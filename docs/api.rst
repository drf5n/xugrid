.. currentmodule:: xugrid

.. _api:

API Reference
=============

This page provides an auto-generated summary of xugrid's API.

Xugrid also almost completely exposes the attributes and methods of xarray
DataArrays and Datasets. Refer to the Xarray documentation.

.. toctree::
   :maxdepth: 1

   changelog

Top-level functions
-------------------

.. autosummary::
   :toctree: api/

    open_dataarray
    open_dataset
    open_mfdataset
    open_zarr
    full_like
    ones_like
    zeros_like
    concat
    merge
    merge_partitions
    burn_vector_geometry
    polygonize

UgridDataArray
--------------

.. autosummary::
   :toctree: api/

    UgridDataArray
    UgridDataArray.ugrid
    UgridDataArray.from_structured

UgridDataset
------------

.. autosummary::
   :toctree: api/

    UgridDataset
    UgridDataset.ugrid
    UgridDataset.from_geodataframe

UGRID Accessor
--------------

These methods and attributes are available under the ``.ugrid`` attribute of a
UgridDataArray or UgridDataset.

.. autosummary::
   :toctree: api/

    UgridDatasetAccessor
    UgridDatasetAccessor.assign_node_coords
    UgridDatasetAccessor.assign_edge_coords
    UgridDatasetAccessor.assign_face_coords
    UgridDatasetAccessor.set_node_coords
    UgridDatasetAccessor.grid
    UgridDatasetAccessor.name
    UgridDatasetAccessor.names
    UgridDatasetAccessor.topology
    UgridDatasetAccessor.bounds
    UgridDatasetAccessor.total_bounds
    UgridDatasetAccessor.crs
    UgridDatasetAccessor.rename
    UgridDatasetAccessor.set_crs
    UgridDatasetAccessor.to_crs
    UgridDatasetAccessor.sel
    UgridDatasetAccessor.sel_points
    UgridDatasetAccessor.intersect_line
    UgridDatasetAccessor.intersect_linestring
    UgridDatasetAccessor.partition
    UgridDatasetAccessor.partition_by_label
    UgridDatasetAccessor.to_geodataframe
    UgridDatasetAccessor.to_dataset
    UgridDatasetAccessor.to_netcdf
    UgridDatasetAccessor.to_zarr

    UgridDataArrayAccessor
    UgridDataArrayAccessor.assign_node_coords
    UgridDataArrayAccessor.assign_edge_coords
    UgridDataArrayAccessor.assign_face_coords
    UgridDataArrayAccessor.set_node_coords
    UgridDataArrayAccessor.grids
    UgridDataArrayAccessor.name
    UgridDataArrayAccessor.names
    UgridDataArrayAccessor.topology
    UgridDataArrayAccessor.bounds
    UgridDataArrayAccessor.total_bounds
    UgridDataArrayAccessor.crs
    UgridDataArrayAccessor.rename
    UgridDataArrayAccessor.set_crs
    UgridDataArrayAccessor.to_crs
    UgridDataArrayAccessor.sel
    UgridDataArrayAccessor.sel_points
    UgridDataArrayAccessor.intersect_line
    UgridDataArrayAccessor.intersect_linestring
    UgridDataArrayAccessor.partition
    UgridDataArrayAccessor.partition_by_label
    UgridDataArrayAccessor.rasterize
    UgridDataArrayAccessor.rasterize_like
    UgridDataArrayAccessor.to_geodataframe
    UgridDataArrayAccessor.binary_dilation
    UgridDataArrayAccessor.binary_erosion
    UgridDataArrayAccessor.connected_components
    UgridDataArrayAccessor.reverse_cuthill_mckee
    UgridDataArrayAccessor.laplace_interpolate
    UgridDataArrayAccessor.to_dataset
    UgridDataArrayAccessor.to_netcdf
    UgridDataArrayAccessor.to_zarr
    

Snapping
--------

Snapping is the process of moving nodes/edges/faces to other
nodes/edges/faces if within a certain range.

.. autosummary::
      :toctree: api/

       snap_to_grid


Regridding
----------

Regridding is the process of converting gridded data from one grid to another
grid. Xugrid provides tools for 2D and 3D regridding of structured gridded
data, represented as xarray objects, as well as (layered) unstructured gridded
data, represented as xugrid objects.

.. autosummary::
      :toctree: api/
       
       BarycentricInterpolator
       CentroidLocatorRegridder
       OverlapRegridder
       RelativeOverlapRegridder

Plotting
--------

These methods are also available under the ``.ugrid.plot`` attribute of a
UgridDataArray.

.. autosummary::
   :toctree: api/

    plot.contour
    plot.contourf
    plot.imshow
    plot.line
    plot.pcolormesh
    plot.scatter
    plot.surface
    plot.tripcolor

UGRID1D Topology
----------------

.. autosummary::
   :toctree: api/

    Ugrid1d

    Ugrid1d.topology_dimension
    Ugrid1d.dimensions
    Ugrid1d.attrs

    Ugrid1d.n_node
    Ugrid1d.node_dimension
    Ugrid1d.node_coordinates
    Ugrid1d.set_node_coords
    Ugrid1d.assign_node_coords
    Ugrid1d.assign_edge_coords

    Ugrid1d.n_edge
    Ugrid1d.edge_dimension
    Ugrid1d.edge_coordinates
    Ugrid1d.edge_x
    Ugrid1d.edge_y

    Ugrid1d.bounds
    Ugrid1d.edge_bounds

    Ugrid1d.node_edge_connectivity
    Ugrid1d.node_node_connectivity

    Ugrid1d.copy
    Ugrid1d.rename

    Ugrid1d.isel
    Ugrid1d.sel
    Ugrid1d.topology_subset
    Ugrid1d.merge_partitions
    Ugrid1d.topological_sort_by_dfs
    Ugrid1d.contract_vertices

    Ugrid1d.from_meshkernel
    Ugrid1d.mesh
    Ugrid1d.meshkernel

    Ugrid1d.set_crs
    Ugrid1d.to_crs

    Ugrid1d.from_dataset
    Ugrid1d.to_dataset
    Ugrid1d.from_geodataframe
    Ugrid1d.to_shapely
    
    Ugrid1d.plot

UGRID2D Topology
----------------

.. autosummary::
   :toctree: api/

    Ugrid2d

    Ugrid2d.topology_dimension
    Ugrid2d.dimensions
    Ugrid2d.attrs

    Ugrid2d.n_node
    Ugrid2d.node_dimension
    Ugrid2d.node_coordinates
    Ugrid2d.set_node_coords
    Ugrid2d.assign_node_coords
    Ugrid2d.assign_edge_coords
    Ugrid2d.assign_face_coords

    Ugrid2d.n_edge
    Ugrid2d.edge_dimension
    Ugrid2d.edge_coordinates
    Ugrid2d.edge_x
    Ugrid2d.edge_y

    Ugrid2d.n_face
    Ugrid2d.face_dimension
    Ugrid2d.face_coordinates
    Ugrid2d.centroids
    Ugrid2d.area
    Ugrid2d.face_x
    Ugrid2d.face_y

    Ugrid2d.bounds
    Ugrid2d.edge_bounds
    Ugrid2d.face_bounds
    Ugrid2d.bounding_polygon

    Ugrid2d.node_node_connectivity
    Ugrid2d.node_edge_connectivity
    Ugrid2d.node_face_connectivity
    Ugrid2d.edge_node_connectivity
    Ugrid2d.face_edge_connectivity
    Ugrid2d.face_face_connectivity
    
    Ugrid2d.validate_edge_node_connectivity

    Ugrid2d.exterior_edges
    Ugrid2d.exterior_faces

    Ugrid2d.copy
    Ugrid2d.rename

    Ugrid2d.triangulate
    Ugrid2d.triangulation
    Ugrid2d.voronoi_topology
    Ugrid2d.centroid_triangulation
    Ugrid2d.tesselate_centroidal_voronoi
    Ugrid2d.tesselate_circumcenter_voronoi
    Ugrid2d.reverse_cuthill_mckee
    Ugrid2d.compute_barycentric_weights

    Ugrid2d.isel
    Ugrid2d.sel
    Ugrid2d.sel_points
    Ugrid2d.intersect_line
    Ugrid2d.intersect_linestring
    Ugrid2d.celltree
    Ugrid2d.locate_points
    Ugrid2d.intersect_edges
    Ugrid2d.locate_bounding_box
    Ugrid2d.rasterize
    Ugrid2d.rasterize_like
    Ugrid2d.topology_subset
    Ugrid2d.label_partitions
    Ugrid2d.partition
    Ugrid2d.merge_partitions

    Ugrid2d.from_meshkernel
    Ugrid2d.mesh
    Ugrid2d.meshkernel

    Ugrid2d.set_crs
    Ugrid2d.to_crs

    Ugrid2d.from_dataset
    Ugrid2d.to_dataset
    Ugrid2d.from_geodataframe
    Ugrid2d.from_structured
    Ugrid2d.from_structured_bounds
    Ugrid2d.to_shapely

    Ugrid2d.plot

UGRID Roles Accessor
--------------------

.. autosummary::
   :toctree: api/

    UgridRolesAccessor
    UgridRolesAccessor.topology
    UgridRolesAccessor.connectivity
    UgridRolesAccessor.coordinates
    UgridRolesAccessor.dimensions
