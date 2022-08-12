import abc
import types
from functools import wraps
from itertools import chain
from typing import Any, Callable, Sequence, Type, Union

import numpy as np
import pandas as pd
import scipy.sparse
import xarray as xr
from xarray.backends.api import DATAARRAY_NAME, DATAARRAY_VARIABLE
from xarray.core._typed_ops import DataArrayOpsMixin, DatasetOpsMixin
from xarray.core.utils import UncachedAccessor, either_dict_or_kwargs

from . import connectivity
from .interpolate import laplace_interpolate
from .plot.plot import _PlotMethods

# from .plot.pyvista import to_pyvista_grid
from .ugrid import AbstractUgrid, Ugrid2d, grid_from_dataset, grid_from_geodataframe

UgridType = Type[AbstractUgrid]


def xarray_wrapper(func, grid):
    """
    runs a function, and if the result is an xarray dataset or an xarray
    dataArray, it creates an UgridDataset or an UgridDataArray around it
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, xr.Dataset):
            return UgridDataset(result, grid)
        elif isinstance(result, xr.DataArray):
            return UgridDataArray(result, grid)
        else:
            return result

    return wrapped


class DunderForwardMixin:
    """
    These methods are not present in the xarray OpsMixin classes.
    """

    def __bool__(self):
        return bool(self.obj)

    def __contains__(self, key: Any):
        return key in self.obj

    def __int__(self):
        return int(self.obj)

    def __float__(self):
        return float(self.obj)


class UgridDataArray(DataArrayOpsMixin, DunderForwardMixin):
    """
    Wraps an xarray DataArray, adding UGRID topology.
    """

    def __repr__(self):
        return self.obj.__repr__()

    def __init__(self, obj: xr.DataArray, grid: UgridType):
        self.grid = grid
        self.obj = obj

    def __getitem__(self, key):
        """
        forward getters to xr.DataArray. Wrap result if necessary
        """
        result = self.obj[key]
        if isinstance(result, xr.DataArray):
            return UgridDataArray(result, self.grid)
        else:
            return result

    def __setitem__(self, key, value):
        """
        forward setters to  xr.DataArray
        """
        self.obj[key] = value

    def __getattr__(self, attr):
        """
        Appropriately wrap result if necessary.
        """
        result = getattr(self.obj, attr)
        if isinstance(result, xr.DataArray):
            return UgridDataArray(result, self.grid)
        elif isinstance(result, types.MethodType):
            return xarray_wrapper(result, self.grid)
        else:
            return result

    def _unary_op(
        self,
        f: Callable,
    ):
        return UgridDataArray(self.obj._unary_op(f), self.grid)

    def _binary_op(
        self,
        other,
        f: Callable,
        reflexive: bool = False,
    ):
        if isinstance(other, (UgridDataArray, UgridDataset)):
            other = other.obj
        return UgridDataArray(self.obj._binary_op(other, f, reflexive), self.grid)

    def _inplace_binary_op(self, other, f: Callable):
        if isinstance(other, (UgridDataArray, UgridDataset)):
            other = other.obj
        return UgridDataArray(self.obj._inplace_binary_op(other, f), self.grid)

    @property
    def ugrid(self):
        """
        UGRID Accessor. This "accessor" makes operations using the UGRID
        topology available.
        """
        return UgridDataArrayAccessor(self.obj, self.grid)

    @staticmethod
    def from_structured(da: xr.DataArray):
        """
        Create a UgridDataArray from a (structured) xarray DataArray.

        The spatial dimensions are flattened into a single UGRID face dimension.

        Parameters
        ----------
        da: xr.DataArray
            Last two dimensions must be ``("y", "x")``.

        Returns
        -------
        unstructured: UgridDataArray
        """
        if da.dims[-2:] != ("y", "x"):
            raise ValueError('Last two dimensions of da must be ("y", "x")')
        grid = Ugrid2d.from_structured(da)
        dims = da.dims[:-2]
        coords = {k: da.coords[k] for k in dims}
        face_da = xr.DataArray(
            da.data.reshape(*da.shape[:-2], -1),
            coords=coords,
            dims=[*dims, grid.face_dimension],
            name=da.name,
        )
        return UgridDataArray(face_da, grid)


class AbstractUgridAccessor(abc.ABC):
    @abc.abstractmethod
    def to_dataset():
        """ """

    @abc.abstractmethod
    def assign_node_coords():
        """ """

    @abc.abstractmethod
    def set_node_coords():
        """ """

    @abc.abstractproperty
    def crs():
        """ """

    @staticmethod
    def _sel(obj, grid, x, y):
        # TODO: also do vectorized indexing like xarray?
        # Might not be worth it, as orthogonal and vectorized indexing are
        # quite confusing.
        dim, ugrid, index, coords = grid.sel(x=x, y=y)
        result = obj.isel({dim: index})

        if not ugrid:
            return result.assign_coords(coords)

        grid = grid.topology_subset(index)
        if isinstance(obj, xr.DataArray):
            return UgridDataArray(result, grid)
        elif isinstance(obj, xr.Dataset):
            return UgridDataset(result, grid)
        else:
            raise TypeError(
                f"Expected UgridDataArray or UgridDataset, got {type(result).__name__}"
            )

    @staticmethod
    def _sel_points(obj, grid, x, y):
        """
        Select points in the unstructured grid.

        Parameters
        ----------
        x: ndarray of floats with shape ``(n_points,)``
        y: ndarray of floats with shape ``(n_points,)``

        Returns
        -------
        points: Union[xr.DataArray, xr.Dataset]
        """
        if grid.topology_dimension != 2:
            raise NotImplementedError
        dim, _, index, coords = grid.sel_points(x, y)
        result = obj.isel({dim: index})
        return result.assign_coords(coords)

    def to_netcdf(self, *args, **kwargs):
        """
        Write dataset contents to a UGRID compliant netCDF file.

        This function wraps :py:meth:`xr.Dataset.to_netcdf`; it adds the UGRID
        variables and coordinates to a standard xarray Dataset, then writes the
        result to a netCDF.

        All arguments are forwarded to :py:meth:`xr.Dataset.to_netcdf`.
        """
        self.to_dataset().to_netcdf(*args, **kwargs)

    def to_zarr(self, *args, **kwargs):
        """
        Write dataset contents to a UGRID compliant Zarr file.

        This function wraps :py:meth:`xr.Dataset.to_zarr`; it adds the UGRID
        variables and coordinates to a standard xarray Dataset, then writes the
        result to a Zarr file.

        All arguments are forwarded to :py:meth:`xr.Dataset.to_zarr`.
        """
        self.to_dataset().to_zarr(*args, **kwargs)


class UgridDataset(DatasetOpsMixin, DunderForwardMixin):
    """
    Wraps an xarray Dataset, adding UGRID topology.
    """

    def __repr__(self):
        return self.obj.__repr__()

    def __init__(
        self, obj: xr.Dataset = None, grids: UgridType | Sequence[UgridType] = None
    ):
        if grids is None:
            if obj is None:
                raise ValueError("At least either obj or grids is required")
            if not isinstance(obj, xr.Dataset):
                raise TypeError(
                    "UgridDataset should be initialized with xarray.Dataset. "
                    f"Received instead: {type(obj)}"
                )
            topologies = obj.ugrid_roles.topology
            grids = [grid_from_dataset(obj, topology) for topology in topologies]
        else:
            # Make sure it's a new list
            if isinstance(grids, (list, tuple, set)):
                grids = [grid for grid in grids]
            else:  # not iterable
                grids = [grids]

        if obj is None:
            ds = xr.Dataset()
        else:
            connectivity_vars = [
                name
                for v in obj.ugrid_roles.connectivity.values()
                for name in v.values()
            ]
            ds = obj.drop_vars(obj.ugrid_roles.topology + connectivity_vars)

        self.grids = grids
        self.obj = ds

    def __contains__(self, key: Any):
        return key in self.obj

    def __getitem__(self, key):
        result = self.obj[key]
        grids = {dim: grid for grid in self.grids for dim in grid.dimensions}
        item_grids = list(set(grids[dim] for dim in result.dims if dim in grids))

        # Now find out which grid to return for this key
        if isinstance(result, xr.DataArray):
            if len(item_grids) == 0:
                return result
            elif len(item_grids) > 1:
                raise RuntimeError("This shouldn't happen. Please open an issue.")
            return UgridDataArray(result, item_grids[0])
        elif isinstance(result, xr.Dataset):
            return UgridDataset(result, item_grids)
        else:
            return result

    def __setitem__(self, key, value):
        # TODO: check with topology
        append = False
        if isinstance(value, UgridDataArray):
            # Check if the dimensions occur in self.
            # if they don't, the grid should be added.
            matching_dims = [
                dim for dim in value.grid.dimensions if dim in self.obj.dims
            ]
            if matching_dims:
                # If they do match: the grids should match.
                grids = {dim: grid for grid in self.grids for dim in grid.dimensions}
                grid_to_match = grids[matching_dims[0]]
                if not grid_to_match.equals(value.grid):
                    raise ValueError("grids do not match")
            else:
                append = True

            self.obj[key] = value.obj
            if append:
                self.grids.append(value.grid)
        else:
            self.obj[key] = value

    def __getattr__(self, attr):
        """
        Appropriately wrap result if necessary.
        """
        result = getattr(self.obj, attr)
        grids = {dim: grid for grid in self.grids for dim in grid.dimensions}
        if isinstance(result, xr.DataArray):
            item_grids = list(set(grids[dim] for dim in result.dims if dim in grids))
            if len(item_grids) == 0:
                return result
            if len(item_grids) > 1:
                raise RuntimeError("This shouldn't happen. Please open an issue.")
            return UgridDataArray(result, item_grids[0])
        elif isinstance(result, xr.Dataset):
            item_grids = list(set(grids[dim] for dim in result.dims if dim in grids))
            return UgridDataset(result, item_grids)
        elif isinstance(result, types.MethodType):
            return xarray_wrapper(result, self.grids)
        else:
            return result

    def _unary_op(
        self,
        f: Callable,
    ):
        return UgridDataset(self.obj._unary_op(f), self.grids)

    def _binary_op(
        self,
        other,
        f: Callable,
        reflexive: bool = False,
    ):
        if isinstance(other, (UgridDataArray, UgridDataset)):
            other = other.obj
        return UgridDataset(self.obj._binary_op(other, f, reflexive), self.grids)

    def _inplace_binary_op(self, other, f: Callable):
        if isinstance(other, (UgridDataArray, UgridDataset)):
            other = other.obj
        return UgridDataset(self.obj._inplace_binary_op(other, f), self.grids)

    @property
    def ugrid(self):
        """
        UGRID Accessor. This "accessor" makes operations using the UGRID
        topology available.
        """
        return UgridDatasetAccessor(self.obj, self.grids)

    @staticmethod
    def from_geodataframe(geodataframe: "geopandas.GeoDataFrame"):  # type: ignore # noqa
        """
        Convert a geodataframe into the appropriate Ugrid topology and dataset.

        Parameters
        ----------
        geodataframe: gpd.GeoDataFrame

        Returns
        -------
        dataset: UGridDataset
        """
        grid = grid_from_geodataframe(geodataframe)
        ds = xr.Dataset.from_dataframe(geodataframe.drop("geometry", axis=1))
        return UgridDataset(ds, [grid])


class UgridDatasetAccessor(AbstractUgridAccessor):
    def __init__(self, obj: xr.Dataset, grids: Sequence[UgridType]):
        self.obj = obj
        self.grids = grids

    def assign_node_coords(self) -> UgridDataset:
        """
        Assign node coordinates from the grid to the object.

        Returns a new object with all the original data in addition to the new
        node coordinates of the grid.

        Returns
        -------
        assigned: UgridDataset
        """
        result = self.obj
        for grid in self.grids:
            result = grid.assign_node_coords(result)
        return UgridDataset(result, self.grids)

    def set_node_coords(self, node_x: str, node_y: str, topology: str = None):
        """
        Given names of x and y coordinates of the nodes of an object, set them
        as the coordinates in the grid.

        Parameters
        ----------
        node_x: str
            Name of the x coordinate of the nodes in the object.
        node_y: str
            Name of the y coordinate of the nodes in the object.
        topology: str, optional
            Name of the grid topology in which to set the node_x and node_y
            coordinates. Can be omitted if the UgridDataset contains only a
            single grid.
        """
        if topology is None:
            if len(self.grids) == 1:
                grid = self.grids[0]
            else:
                raise ValueError(
                    "topology must be specified when dataset contains multiple datasets"
                )
        else:
            grids = [grid for grid in self.grid if grid.name == topology]
            if len(grids != 1):
                raise ValueError(
                    f"Expected one grid with topology {topology}, found: {len(grids)}"
                )
            grid = grids[0]

        grid.set_node_coords(node_x, node_y, self.obj)

    def isel(self, indexers, **indexers_kwargs):
        """
        Returns a new object with arrays indexed along edges or faces.

        Parameters
        ----------
        indexer: 1d array of integer or bool

        Returns
        -------
        indexed: Union[UgridDataArray, UgridDataset]
        """
        indexers = either_dict_or_kwargs(indexers, indexers_kwargs, "isel")
        alldims = set(chain.from_iterable([grid.dimensions for grid in self.grids]))
        invalid = indexers.keys() - alldims
        if invalid:
            raise ValueError(
                f"Dimensions {invalid} do not exist. Expected one of {alldims}"
            )

        if len(indexers) > 1:
            raise NotImplementedError("Can only index a single dimension at a time")
        dim, indexer = next(iter(indexers.items()))

        # Find grid to use for selection
        grids = [
            grid.isel(dim, indexer) if dim in grid.dimensions else grid
            for grid in self.grids
        ]
        result = self.obj.isel({dim: indexer})

        if isinstance(self.obj, xr.Dataset):
            return UgridDataset(result, grids)
        else:
            raise TypeError(f"Expected UgridDataset, got {type(result).__name__}")

    def sel(self, x=None, y=None):
        result = self.obj
        for grid in self.grids:
            result = self._sel(result, grid, x, y)
        return result

    def sel_points(self, x, y):
        result = self.obj
        for grid in self.grids:
            result = self._sel_points(result, grid, x, y)
        return result

    def to_dataset(self):
        """
        Converts this UgridDataArray or UgridDataset into a standard
        xarray.Dataset.

        The UGRID topology information is added as standard data variables.

        Returns
        -------
        dataset: UgridDataset
        """
        return xr.merge([grid.to_dataset(self.obj) for grid in self.grids])

    @property
    def crs(self):
        """
        The Coordinate Reference System (CRS) represented as a ``pyproj.CRS`` object.

        Returns None if the CRS is not set.

        Returns
        -------
        crs: dict
            A dictionary containing the names of the grids and their CRS.
        """
        return {grid.name: grid.crs for grid in self.grids}

    def to_geodataframe(
        self, dim_order=None
    ) -> "geopandas.GeoDataFrame":  # type: ignore # noqa
        """
        Convert data and topology of one facet (node, edge, face) of the grid
        to a geopandas GeoDataFrame. This also determines the geometry type of
        the geodataframe:

        * node: point
        * edge: line
        * face: polygon

        Parameters
        ----------
        name: str
            Name to give to the array (required if unnamed).
        dim_order:
            Hierarchical dimension order for the resulting dataframe. Array content is
            transposed to this order and then written out as flat vectors in contiguous
            order, so the last dimension in this list will be contiguous in the resulting
            DataFrame. This has a major influence on which operations are efficient on the
            resulting dataframe.

            If provided, must include all dimensions of this DataArray. By default,
            dimensions are sorted according to the DataArray dimensions order.

        Returns
        -------
        geodataframe: gpd.GeoDataFrame
        """
        import geopandas as gpd

        ds = self.obj

        gdfs = []
        for grid in self.grids:
            if grid.topology_dimension == 1:
                dim = grid.edge_dimension
            elif grid.topology_dimension == 2:
                dim = grid.face_dimension
            else:
                raise ValueError("invalid topology dimension on grid")

            variables = [var for var in ds.data_vars if dim in ds[var].dims]
            # TODO deal with time-dependent data, etc.
            # Basically requires checking which variables are static, which aren't.
            # For non-static, requires repeating all geometries.
            # Call reset_index on multi-index to generate them as regular columns.
            gdfs.append(
                gpd.GeoDataFrame(
                    data=ds[variables].to_dataframe(dim_order=dim_order),
                    geometry=grid.to_pygeos(dim),
                )
            )

        return pd.concat(gdfs)


class UgridDataArrayAccessor(AbstractUgridAccessor):
    """
    This "accessor" makes operations using the UGRID topology available via the
    ``.ugrid`` attribute for UgridDataArrays and UgridDatasets.
    """

    def __init__(self, obj: xr.DataArray, grid: UgridType):
        self.obj = obj
        self.grid = grid

    plot = UncachedAccessor(_PlotMethods)

    def assign_node_coords(self) -> xr.DataArray:
        """
        Assign node coordinates from the grid to the object.

        Returns a new object with all the original data in addition to the new
        node coordinates of the grid.

        Returns
        -------
        assigned: UgridDataset
        """
        return UgridDataArray(self.grid.assign_node_coords(self.obj), self.grid)

    def set_node_coords(self, node_x: str, node_y: str):
        """
        Given names of x and y coordinates of the nodes of an object, set them
        as the coordinates in the grid.

        Parameters
        ----------
        node_x: str
            Name of the x coordinate of the nodes in the object.
        node_y: str
            Name of the y coordinate of the nodes in the object.
        """
        self.grid.set_node_coords(node_x, node_y, self.obj)

    def isel(self, indexers, **indexers_kwargs):
        """
        Returns a new object with arrays indexed along edges or faces.

        Parameters
        ----------
        indexer: 1d array of integer or bool

        Returns
        -------
        indexed: Union[UgridDataArray, UgridDataset]
        """
        indexers = either_dict_or_kwargs(indexers, indexers_kwargs, "isel")
        dims = self.grid.dimensions
        invalid = indexers.keys() - set(dims)
        if invalid:
            raise ValueError(
                f"Dimensions {invalid} do not exist. Expected one of {dims}"
            )

        if len(indexers) > 1:
            raise NotImplementedError("Can only index a single dimension at a time")
        dim, indexer = next(iter(indexers.items()))

        result = self.obj.isel({dim: indexer})
        grid = self.grid.isel(dim, indexer)
        if isinstance(self.obj, xr.DataArray):
            return UgridDataArray(result, grid)
        else:
            raise TypeError(f"Expected UgridDataArray, got {type(result).__name__}")

    def sel(self, x=None, y=None):
        """
        Returns a new object, a subselection in the UGRID x and y coordinates.

        The indexing for x and y always occurs orthogonally, i.e.:
        ``.sel(x=[0.0, 5.0], y=[10.0, 15.0])`` results in a four points. For
        vectorized indexing (equal to ``zip``ing through x and y), see
        ``.sel_points``.

        Depending on the nature of the x and y indexers, a xugrid or xarray
        object is returned:

        * slice without step: ``x=slice(-100, 100)``: returns xugrid object, a
          part of the unstructured grid.
        * slice with step: ``x=slice(-100, 100, 10)``: returns xarray object, a
          series of points (x=[-100, -90, -80, ..., 90, 100]).
        * a scalar: ``x=5.0``: returns xarray object, a point.
        * an array: ``x=[1.0, 15.0, 17.0]``: returns xarray object, a series of
          points.

        Parameters
        ----------
        x: float, 1d array, slice
        y: float, 1d array, slice

        Returns
        -------
        selection: Union[UgridDataArray, UgridDataset, xr.DataArray, xr.Dataset]
        """
        return self._sel(self.obj, self.grid, x, y)

    def sel_points(self, x, y):
        """
        Select points in the unstructured grid.

        Parameters
        ----------
        x: ndarray of floats with shape ``(n_points,)``
        y: ndarray of floats with shape ``(n_points,)``

        Returns
        -------
        points: Union[xr.DataArray, xr.Dataset]
        """
        return self._sel_points(self.obj, self.grid, x, y)

    def _raster(self, x, y, index) -> xr.DataArray:
        index = index.ravel()
        data = self.obj.isel({self.grid.face_dimension: index}).astype(float).values
        data[index == -1] = np.nan
        out = xr.DataArray(
            data=data.reshape(y.size, x.size),
            coords={"y": y, "x": x},
            dims=["y", "x"],
        )
        return out

    def rasterize(self, resolution: float):
        """
        Rasterize unstructured grid by sampling.

        Parameters
        ----------
        resolution: float
            Spacing in x and y.

        Returns
        -------
        rasterized: Union[xr.DataArray, xr.Dataset]
        """
        x, y, index = self.grid.rasterize(resolution)
        return self._raster(x, y, index)

    def rasterize_like(self, other: Union[xr.DataArray, xr.Dataset]):
        """
        Rasterize unstructured grid by sampling on the x and y coordinates
        of ``other``.

        Parameters
        ----------
        resolution: float
            Spacing in x and y.
        other: Union[xr.DataArray, xr.Dataset]
            Object to take x and y coordinates from.

        Returns
        -------
        rasterized: Union[xr.DataArray, xr.Dataset]
        """
        x, y, index = self.grid.rasterize_like(
            x=other["x"].values,
            y=other["y"].values,
        )
        return self._raster(x, y, index)

    @property
    def crs(self):
        """
        The Coordinate Reference System (CRS) represented as a ``pyproj.CRS`` object.

        Returns None if the CRS is not set.

        Returns
        -------
        crs: dict
            A dictionary containing the name of the grid and its CRS.
        """
        return {self.grid.name: self.grid.crs}

    def to_geodataframe(
        self, name: str = None, dim_order=None
    ) -> "geopandas.GeoDataFrame":  # type: ignore # noqa
        """
        Convert data and topology of one facet (node, edge, face) of the grid
        to a geopandas GeoDataFrame. This also determines the geometry type of
        the geodataframe:

        * node: point
        * edge: line
        * face: polygon

        Parameters
        ----------
        dim: str
            node, edge, or face dimension. Inferred for DataArray.
        name: str
            Name to give to the array (required if unnamed).
        dim_order:
            Hierarchical dimension order for the resulting dataframe. Array content is
            transposed to this order and then written out as flat vectors in contiguous
            order, so the last dimension in this list will be contiguous in the resulting
            DataFrame. This has a major influence on which operations are efficient on the
            resulting dataframe.

            If provided, must include all dimensions of this DataArray. By default,
            dimensions are sorted according to the DataArray dimensions order.

        Returns
        -------
        geodataframe: gpd.GeoDataFrame
        """
        import geopandas as gpd

        dim = self.obj.dims[-1]
        if name is not None:
            ds = self.obj.to_dataset(name=name)
        else:
            ds = self.obj.to_dataset()

        variables = [var for var in ds.data_vars if dim in ds[var].dims]
        # TODO deal with time-dependent data, etc.
        # Basically requires checking which variables are static, which aren't.
        # For non-static, requires repeating all geometries.
        # Call reset_index on multi-index to generate them as regular columns.
        df = ds[variables].to_dataframe(dim_order=dim_order)
        geometry = self.grid.to_pygeos(dim)
        return gpd.GeoDataFrame(df, geometry=geometry)

    def _binary_iterate(self, iterations: int, mask, value, border_value):
        if border_value == value:
            exterior = self.grid.exterior_faces
        else:
            exterior = None
        if mask is not None:
            mask = mask.values

        obj = self.obj
        if isinstance(obj, xr.DataArray):
            output = connectivity._binary_iterate(
                self.grid.face_face_connectivity,
                obj.values,
                value,
                iterations,
                mask,
                exterior,
                border_value,
            )
            da = obj.copy(data=output)
            return UgridDataArray(da, self.grid.copy())
        elif isinstance(obj, xr.Dataset):
            raise NotImplementedError
        else:
            raise ValueError("object should be a xr.DataArray")

    def binary_dilation(
        self,
        iterations: int = 1,
        mask=None,
        border_value=False,
    ):
        """
        Binary dilation can be used on a boolean array to expand the "shape" of
        features.

        Compare with :py:func:`scipy.ndimage.binary_dilation`.

        Parameters
        ----------
        iterations: int, default: 1
        mask: 1d array of bool, optional
        border_value: bool, default value: False

        Returns
        -------
        dilated: UgridDataArray
        """
        return self._binary_iterate(iterations, mask, True, border_value)

    def binary_erosion(
        self,
        iterations: int = 1,
        mask=None,
        border_value=False,
    ):
        """
        Binary erosion can be used on a boolean array to shrink the "shape" of
        features.

        Compare with :py:func:`scipy.ndimage.binary_erosion`.

        Parameters
        ----------
        iterations: int, default: 1
        mask: 1d array of bool, optional
        border_value: bool, default value: False

        Returns
        -------
        eroded: UgridDataArray
        """
        return self._binary_iterate(iterations, mask, False, border_value)

    def connected_components(self):
        """
        Every edge or face is given a component number. If all are connected,
        all will have the same number.

        Wraps :py:func:`scipy.sparse.csgraph.connected_components``.

        Returns
        -------
        labelled: UgridDataArray
        """
        _, labels = scipy.sparse.csgraph.connected_components(
            self.grid.face_face_connectivity
        )
        return UgridDataArray(
            xr.DataArray(labels, dims=[self.grid.face_dimension]),
            self.grid,
        )

    def reverse_cuthill_mckee(self):
        """
        Reduces bandwith of the connectivity matrix.

        Wraps :py:func:`scipy.sparse.csgraph.reverse_cuthill_mckee`.

        Returns
        -------
        reordered: Union[UgridDataArray, UgridDataset]
        """
        grid = self.grid
        reordered_grid, reordering = self.grid.reverse_cuthill_mckee()
        reordered_data = self.obj.isel({grid.face_dimension: reordering})
        # TODO: this might not work properly if e.g. centroids are stored in obj.
        # Not all metadata would be reordered.
        return UgridDataArray(
            reordered_data,
            reordered_grid,
        )

    def laplace_interpolate(
        self,
        xy_weights: bool = True,
        direct_solve: bool = False,
        drop_tol: float = None,
        fill_factor: float = None,
        drop_rule: str = None,
        options: dict = None,
        tol: float = 1.0e-5,
        maxiter: int = 250,
    ):
        """
        Fill gaps in ``data`` (``np.nan`` values) using Laplace interpolation.

        This solves Laplace's equation where where there is no data, with data
        values functioning as fixed potential boundary conditions.

        Note that an iterative solver method will be required for large grids.
        In this case, some experimentation with the solver settings may be
        required to find a converging solution of sufficient accuracy. Refer to
        the documentation of :py:func:`scipy.sparse.linalg.spilu` and
        :py:func:`scipy.sparse.linalg.cg`.

        Parameters
        ----------
        xy_weights: bool, default False.
            Wether to use the inverse of the centroid to centroid distance in
            the coefficient matrix. If ``False``, defaults to uniform
            coefficients of 1 so that each face connection has equal weight.
        direct_solve: bool, optional, default ``False``
            Whether to use a direct or an iterative solver or a conjugate gradient
            solver. Direct method provides an exact answer, but are unsuitable
            for large problems.
        drop_tol: float, optional, default None.
            Drop tolerance for ``scipy.sparse.linalg.spilu`` which functions as a
            preconditioner for the conjugate gradient solver.
        fill_factor: float, optional, default None.
            Fill factor for ``scipy.sparse.linalg.spilu``.
        drop_rule: str, optional default None.
            Drop rule for ``scipy.sparse.linalg.spilu``.
        options: dict, optional, default None.
            Remaining other options for ``scipy.sparse.linalg.spilu``.
        tol: float, optional, default 1.0e-5.
            Convergence tolerance for ``scipy.sparse.linalg.cg``.
        maxiter: int, default 250.
            Maximum number of iterations for ``scipy.sparse.linalg.cg``.

        Returns
        -------
        filled: UgridDataArray of floats
        """
        grid = self.grid
        da = self.obj
        if grid.topology_dimension != 2:
            raise NotImplementedError
        if len(da.dims) > 1 or da.dims[0] != grid.face_dimension:
            raise NotImplementedError

        connectivity = grid.face_face_connectivity.copy()
        if xy_weights:
            xy = grid.centroids
            coo = connectivity.tocoo()
            i = coo.row
            j = coo.col
            connectivity.data = 1.0 / np.linalg.norm(xy[j] - xy[i], axis=1)

        filled = laplace_interpolate(
            connectivity=connectivity,
            data=da.values,
            use_weights=xy_weights,
            direct_solve=direct_solve,
            drop_tol=drop_tol,
            fill_factor=fill_factor,
            drop_rule=drop_rule,
            options=options,
            tol=tol,
            maxiter=maxiter,
        )
        da_filled = da.copy(data=filled)
        return UgridDataArray(da_filled, grid)

    def to_dataset(self):
        """
        Converts this UgridDataArray or UgridDataset into a standard
        xarray.Dataset.

        The UGRID topology information is added as standard data variables.

        Returns
        -------
        dataset: UgridDataset
        """
        return self.grid.to_dataset(self.obj)


# Wrapped IO methods
# ------------------


def open_dataset(*args, **kwargs):
    ds = xr.open_dataset(*args, **kwargs)
    return UgridDataset(ds)


def open_dataarray(*args, **kwargs):
    ds = xr.open_dataset(*args, **kwargs)
    dataset = UgridDataset(ds)

    if len(dataset.data_vars) != 1:
        raise ValueError(
            "Given file dataset contains more than one data "
            "variable. Please read with xarray.open_dataset and "
            "then select the variable you want."
        )
    else:
        (data_array,) = dataset.data_vars.values()

    data_array.set_close(dataset._close)

    # Reset names if they were changed during saving
    # to ensure that we can 'roundtrip' perfectly
    if DATAARRAY_NAME in dataset.attrs:
        data_array.name = dataset.attrs[DATAARRAY_NAME]
        del dataset.attrs[DATAARRAY_NAME]

    if data_array.name == DATAARRAY_VARIABLE:
        data_array.name = None

    return data_array


def open_mfdataset(*args, **kwargs):
    if "data_vars" in kwargs:
        raise ValueError("data_vars kwargs is not supported in xugrid.open_mfdataset")
    kwargs["data_vars"] = "minimal"
    ds = xr.open_mfdataset(*args, **kwargs)
    return UgridDataset(ds)


def open_zarr(*args, **kwargs):
    ds = xr.open_zarr(*args, **kwargs)
    return UgridDataset(ds)


open_dataset.__doc__ = xr.open_dataset.__doc__
open_dataarray.__doc__ = xr.open_dataarray.__doc__
open_mfdataset.__doc__ = xr.open_mfdataset.__doc__
open_zarr.__doc__ = xr.open_zarr.__doc__


# Other utilities
# ---------------


def wrap_func_like(func):
    @wraps(func)
    def _like(other, *args, **kwargs):
        obj = func(other.obj, *args, **kwargs)
        if isinstance(obj, xr.DataArray):
            return type(other)(obj, other.grid)
        elif isinstance(obj, xr.Dataset):
            return type(other)(obj, other.grids)
        else:
            raise TypeError(
                f"Expected Dataset or DataArray, received {type(other).__name__}"
            )

    _like.__doc__ = func.__doc__
    return _like


full_like = wrap_func_like(xr.full_like)
zeros_like = wrap_func_like(xr.zeros_like)
ones_like = wrap_func_like(xr.ones_like)
