from pathlib import Path
import unittest

try:
    from image_viewer.slideshow import SlideshowState, apply_navigation
    from image_viewer.sources import ImageEntry, ImageSource
except ModuleNotFoundError as exc:  # pragma: no cover - env dependent
    if exc.name == "PIL":
        raise unittest.SkipTest("Pillow not installed in this environment") from exc
    raise


class DummySource(ImageSource):
    def list_images(self):
        return []

    def open_image(self, entry):
        raise NotImplementedError

    def container_dir(self) -> Path:
        return Path.cwd()


def build_state(index: int = 0, total: int = 4) -> SlideshowState:
    images = [ImageEntry(kind="file", path=Path(f"image_{i}.jpg")) for i in range(total)]
    return SlideshowState(source=DummySource(), images=images, index=index)


class SlideshowNavigationTests(unittest.TestCase):
    def test_prev_on_first_image_requests_close(self) -> None:
        state = build_state(index=0)
        self.assertEqual(apply_navigation(state, "prev"), "close")
        self.assertEqual(state.index, 0)

    def test_next_on_last_image_requests_close(self) -> None:
        state = build_state(index=3)
        self.assertEqual(apply_navigation(state, "next"), "close")
        self.assertEqual(state.index, 3)

    def test_up_moves_to_first_image(self) -> None:
        state = build_state(index=2)
        self.assertEqual(apply_navigation(state, "first"), "show")
        self.assertEqual(state.index, 0)

    def test_down_moves_to_last_image(self) -> None:
        state = build_state(index=1)
        self.assertEqual(apply_navigation(state, "last"), "show")
        self.assertEqual(state.index, 3)

    def test_navigation_queue_is_limited_to_three_inputs(self) -> None:
        state = build_state(index=1)
        self.assertTrue(state.enqueue_navigation("next"))
        self.assertTrue(state.enqueue_navigation("next"))
        self.assertTrue(state.enqueue_navigation("prev"))
        self.assertFalse(state.enqueue_navigation("first"))
        self.assertEqual(list(state.pending_navigation), ["next", "next", "prev"])


if __name__ == "__main__":
    unittest.main()
