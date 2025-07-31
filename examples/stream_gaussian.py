"""
Example usage of `napari-serverkit` to run a filter (here, a simple gaussian filter) in tiles on an input image.
"""
from skimage.filters import gaussian
import napari
import imaging_server_kit as sk
from napari_serverkit import AlgorithmWidget


@sk.algorithm_server(
    algorithm_name="stream-gaussian",
    title="Gaussian filter applied in 2D tiles",
    parameters={
        "image": sk.ImageUI(dimensionality=[2, 3]),
        "sigma": sk.FloatUI("Sigma", default=1.0, min=0.0, max=10.0, step=0.1),
        "tile_size": sk.IntUI("Tile size", default=128, min=1, max=2048, step=16),
        "overlap_percent": sk.FloatUI("Overlap %", default=0, min=0, max=1),
        "delay_sec": sk.FloatUI("Delay (sec)", default=0, min=0, max=1, step=0.1),
    },
    sample_images=["/home/wittwer/data/test_images/C3-bigimg-gray-inv-crop.tif"],
)
def stream_gaussian(image, sigma, tile_size_px, overlap_percent, delay_sec):
    if image.ndim == 2:
        tiling_func = sk.image_tile_generator_2D
    elif image.ndim == 3:
        tiling_func = sk.image_tile_generator_3D
    
    for image_tile, tile_meta in tiling_func(
        image, tile_size_px, overlap_percent, delay_sec
    ):
        yield [
            (
                gaussian(image_tile, sigma=sigma),
                {
                    "name": "Gaussian filtered",
                }
                | tile_meta,
                "image",
            )
        ]

if __name__ == "__main__":
    viewer = napari.Viewer()
    widget = AlgorithmWidget(viewer, stream_gaussian)
    viewer.window.add_dock_widget(widget)
    napari.run()
