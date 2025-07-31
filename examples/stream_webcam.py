"""
Example usage of `napari-serverkit` to implement a live stream from a USB camera (e.g. a webcam) into the Napari viewer.
"""
import cv2
import numpy as np
import napari
import imaging_server_kit as sk
from napari_serverkit import AlgorithmWidget


class VideoCamera:
    def __init__(self, video_idx: int):
        self.video = cv2.VideoCapture(video_idx)

    def __del__(self):
        self.video.release()

    def get_frame(self) -> np.ndarray:
        success, image = self.video.read()
        if not success:
            raise RuntimeError("Failed to capture frame from camera")

        image = image[..., ::-1]  # BGR => RGB

        return image


@sk.algorithm_server(
    algorithm_name="webcam-streaming",
    parameters={"webcam_idx": sk.IntUI("Webcam index")},
)
def stream_webcam(webcam_idx):
    camera = VideoCamera(webcam_idx)
    while True:
        frame = camera.get_frame()
        yield [(frame, {"name": "Webcam stream"}, "image")]


if __name__ == "__main__":
    viewer = napari.Viewer()
    widget = AlgorithmWidget(viewer, stream_webcam)
    viewer.window.add_dock_widget(widget)
    napari.run()
