import geopandas as gpd
import numpy as np
import pytest
import shapely
import xarray as xr

from xugrid import conversion as cv


@pytest.fixture(scope="function")
def line():
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 0.0])
    edge_node_connectivity = np.array(
        [
            [0, 1],
            [1, 2],
        ]
    )
    return x, y, edge_node_connectivity


@pytest.fixture(scope="function")
def line_gdf():
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 0.0])
    gdf = gpd.GeoDataFrame(geometry=[shapely.linestrings(x, y)])
    return gdf


@pytest.fixture(scope="function")
def triangle_mesh():
    x = np.array([0.0, 1.0, 1.0, 2.0])
    y = np.array([0.0, 0.0, 1.0, 0.0])
    fill_value = -1
    # Two triangles
    faces = np.array(
        [
            [0, 1, 2],
            [1, 3, 2],
        ]
    )
    return x, y, faces, fill_value


@pytest.fixture(scope="function")
def mixed_mesh():
    x = np.array([0.0, 1.0, 1.0, 2.0, 2.0])
    y = np.array([0.0, 0.0, 1.0, 0.0, 1.0])
    fill_value = -1
    # Triangle, quadrangle
    faces = np.array(
        [
            [0, 1, 2, fill_value],
            [1, 3, 4, 2],
        ]
    )
    return x, y, faces, fill_value


@pytest.fixture(scope="function")
def structured_mesh_ascending():
    da = xr.DataArray(
        data=np.arange(12).reshape((3, 4)),
        coords={"y": [5.0, 10.0, 15.0], "x": [2.0, 4.0, 6.0, 8.0]},
        dims=["y", "x"],
        name="grid",
    )
    return da


@pytest.fixture(scope="function")
def structured_mesh_descending():
    da = xr.DataArray(
        data=np.arange(12).reshape((3, 4)),
        coords={"y": [15.0, 10.0, 5.0], "x": [8.0, 6.0, 4.0, 2.0]},
        dims=["y", "x"],
        name="grid",
    )
    return da


def test_nodes_geos_roundtrip(line):
    x, y, _ = line
    actual = cv.nodes_to_points(x, y)
    x_back, y_back = cv.points_to_nodes(actual)
    points_back = cv.nodes_to_points(x_back, y_back)
    assert np.array_equal(x, x_back)
    assert np.array_equal(y, y_back)
    assert np.array_equal(actual, points_back)


def test_linestrings_to_edges(line_gdf):
    x, y, segments = cv.linestrings_to_edges(line_gdf.geometry.values)
    assert np.allclose(x, [0.0, 1.0, 2.0])
    assert np.allclose(y, [0.0, 0.0, 0.0])
    assert np.array_equal(segments, [[0, 1], [1, 2]])


def test_edges_geos_roundtrip(line):
    x, y, c = line
    actual = cv.edges_to_linestrings(x, y, c)
    x_back, y_back, c_back = cv.linestrings_to_edges(actual)
    lines_back = cv.edges_to_linestrings(x_back, y_back, c_back)
    assert np.array_equal(x, x_back)
    assert np.array_equal(y, y_back)
    assert np.array_equal(c, c_back)
    assert np.array_equal(actual, lines_back)


# Cannot use fixtures in parametrize:
# https://github.com/pytest-dev/pytest/issues/349
def _faces_geos_roundtrip(mesh):
    x, y, c, fv = mesh
    actual = cv.faces_to_polygons(x, y, c, fv)
    x_back, y_back, c_back, fv_back = cv.polygons_to_faces(actual)
    polygons_back = cv.faces_to_polygons(x_back, y_back, c_back, fv_back)
    assert np.array_equal(x, x_back)
    assert np.array_equal(y, y_back)
    assert np.array_equal(c, c_back)
    assert fv == fv_back
    assert np.array_equal(actual, polygons_back)


def test_faces_geos_roundtrip__triangle(triangle_mesh):
    _faces_geos_roundtrip(triangle_mesh)


def test_faces_geos_roundtrip__mixed(mixed_mesh):
    _faces_geos_roundtrip(mixed_mesh)


def test_scalar_spacing(structured_mesh_ascending, structured_mesh_descending):
    upcoords = structured_mesh_ascending.coords["x"]
    downcoords = structured_mesh_descending.coords["x"]
    spacing = xr.DataArray(0.1, name="dx")
    with pytest.raises(ValueError, match="spacing of x does not match value of dx"):
        cv._scalar_spacing(upcoords, spacing)

    spacing = xr.DataArray(2.0, name="dx")
    assert np.allclose(cv._scalar_spacing(upcoords, spacing), 1.0)
    spacing = xr.DataArray(-2.0, name="dx")
    assert np.allclose(cv._scalar_spacing(downcoords, spacing), 1.0)


def test_array_spacing(structured_mesh_ascending, structured_mesh_descending):
    upcoords = structured_mesh_ascending.coords["x"]
    downcoords = structured_mesh_descending.coords["x"]
    spacing = xr.DataArray([0.1], name="dx")
    with pytest.raises(ValueError, match="size of x does not match size of dx"):
        cv._array_spacing(upcoords, spacing)

    spacing = xr.DataArray([2.0, 2.0, 2.0, 2.0], name="dx")
    assert np.allclose(cv._array_spacing(upcoords, spacing), 1.0)
    spacing = xr.DataArray([-2.0, -2.0, -2.0, -2.0], name="dx")
    assert np.allclose(cv._array_spacing(downcoords, spacing), 1.0)


def test_implicit_spacing(structured_mesh_ascending, structured_mesh_descending):
    da = xr.DataArray(
        [[0.0, 0.0]],
        {"y": [0.0], "x": [1.0, 2.0]},
        ["y", "x"],
    )
    with pytest.raises(ValueError, match="Cannot derive spacing of 1-sized coordinate"):
        cv._implicit_spacing(da.coords["y"])

    upcoords = structured_mesh_ascending.coords["x"]
    downcoords = structured_mesh_descending.coords["x"]
    assert np.allclose(cv._implicit_spacing(upcoords), 1.0)
    assert np.allclose(cv._implicit_spacing(downcoords), 1.0)


@pytest.mark.parametrize("spacing_type", ["implicit", "scalar", "array"])
def test_infer_bounds(
    structured_mesh_ascending, structured_mesh_descending, spacing_type
):
    up = structured_mesh_ascending
    down = structured_mesh_descending
    x_expected = np.array(
        [
            [1.0, 3.0],
            [3.0, 5.0],
            [5.0, 7.0],
            [7.0, 9.0],
        ]
    )
    y_expected = np.array(
        [
            [2.5, 7.5],
            [7.5, 12.5],
            [12.5, 17.5],
        ]
    )

    if spacing_type == "scalar":
        up = up.assign_coords({"dx": 2.0, "dy": 5.0})
        down = down.assign_coords({"dx": 2.0, "dy": 5.0})
    elif spacing_type == "array":
        up = up.assign_coords({"dx": ("x", [2.0] * 4), "dy": ("y", [5.0] * 3)})
        down = down.assign_coords({"dx": ("x", [2.0] * 4), "dy": ("y", [5.0] * 3)})

    assert np.allclose(cv.infer_bounds(up, "x"), x_expected)
    assert np.allclose(cv.infer_bounds(up, "y"), y_expected)
    assert np.allclose(cv.infer_bounds(down, "x"), x_expected[::-1])
    assert np.allclose(cv.infer_bounds(down, "y"), y_expected[::-1])


def test_infer_bounds_errors(structured_mesh_ascending):
    up = structured_mesh_ascending
    up = up.assign_coords(x=[2.0, 4.0, 3.0, 8.0])

    with pytest.raises(ValueError, match="x is not monotonic"):
        cv.infer_bounds(up, "x")


def test_bounds_to_vertices(structured_mesh_ascending, structured_mesh_descending):
    with pytest.raises(ValueError, match="Bounds are not monotonic"):
        cv.bounds_to_vertices(
            xr.DataArray(
                data=[[0.0, 1.0], [2.0, 3.0], [1.0, 2.0]], dims=["x", "nbound"]
            )
        )

    up = structured_mesh_ascending
    down = structured_mesh_descending
    x_vertices = np.array([1.0, 3.0, 5.0, 7.0, 9.0])
    y_vertices = np.array([2.5, 7.5, 12.5, 17.5])
    # Ascending
    x_bounds = cv.infer_bounds(up, "x")
    y_bounds = cv.infer_bounds(up, "y")
    assert np.allclose(cv.bounds_to_vertices(x_bounds), x_vertices)
    assert np.allclose(cv.bounds_to_vertices(y_bounds), y_vertices)
    # Descending
    x_bounds = cv.infer_bounds(down, "x")
    y_bounds = cv.infer_bounds(down, "y")
    assert np.allclose(cv.bounds_to_vertices(x_bounds), x_vertices[::-1])
    assert np.allclose(cv.bounds_to_vertices(y_bounds), y_vertices[::-1])


def test_infer_xy_coords():
    da = xr.DataArray(
        data=[[1]],
        coords={"y": [1], "x": [1]},
        dims=["y", "x"],
    )
    assert cv.infer_xy_coords(da) == ("x", "y")

    da = xr.DataArray(
        data=[[1]],
        coords={"latitude": [1], "longitude": [1]},
        dims=["latitude", "longitude"],
    )
    assert cv.infer_xy_coords(da) == ("longitude", "latitude")

    da = xr.DataArray(
        data=[[1]],
        coords={"lat": [1], "lon": [1]},
        dims=["lat", "lon"],
    )
    assert cv.infer_xy_coords(da) == (None, None)

    da["lon"].attrs["axis"] = "X"
    da["lat"].attrs["axis"] = "Y"

    da = xr.DataArray(
        data=[[1]],
        coords={"lat": [1], "lon": [1]},
        dims=["lat", "lon"],
    )
    da["lon"].attrs["standard_name"] = "longitude"
    da["lat"].attrs["standard_name"] = "latitude"
    assert cv.infer_xy_coords(da) == ("lon", "lat")

    da = xr.DataArray(
        data=[[1]],
        coords={"yy": [1], "xx": [1]},
        dims=["yy", "xx"],
    )
    da["xx"].attrs["standard_name"] = "projection_x_coordinate"
    da["yy"].attrs["standard_name"] = "projection_y_coordinate"
    assert cv.infer_xy_coords(da) == ("xx", "yy")
