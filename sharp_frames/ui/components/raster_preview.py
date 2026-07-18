"""Raster-only inline frame preview with a terminal capability fallback."""

from pathlib import Path
from typing import Optional, Type

from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static


def _detect_raster_backend() -> tuple[Optional[Type[Widget]], Optional[str]]:
    """Return a real raster widget supported by the active terminal.

    ``textual-image`` also offers character-cell renderers. Those are
    deliberately excluded: an inline preview is only considered available
    when the terminal reports Sixel or Kitty graphics support.
    """
    try:
        from textual_image.renderable import Image as DetectedRenderable
        from textual_image.renderable.sixel import Image as SixelRenderable
        from textual_image.renderable.tgp import Image as TGPRenderable
    except (ImportError, OSError):
        return None, None

    try:
        if DetectedRenderable is SixelRenderable:
            from textual_image.widget import SixelImage

            return SixelImage, "Sixel"
        if DetectedRenderable is TGPRenderable:
            from textual_image.widget import TGPImage

            return TGPImage, "Kitty graphics"
    except Exception:
        # Terminal capability probing is best effort. A failed query must not
        # prevent the application from starting or its external fallback from
        # working.
        return None, None
    return None, None


RASTER_WIDGET_TYPE, RASTER_BACKEND_NAME = _detect_raster_backend()
_DEFAULT_BACKEND = object()


class RasterImagePreview(Widget):
    """Display a source image through a terminal raster graphics protocol."""

    can_focus = False

    def __init__(
        self,
        *,
        backend_type=_DEFAULT_BACKEND,
        backend_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if backend_type is _DEFAULT_BACKEND:
            self._backend_type = RASTER_WIDGET_TYPE
            self.backend_name = RASTER_BACKEND_NAME
        else:
            self._backend_type = backend_type
            self.backend_name = backend_name
        self.current_path: Optional[Path] = None
        self.display = False

        if self._backend_type is None:
            self.add_class("-unsupported")

    @property
    def raster_supported(self) -> bool:
        """Whether the terminal has a usable raster graphics protocol."""
        return self._backend_type is not None

    def compose(self) -> ComposeResult:
        """Create either the raster canvas or a compact fallback notice."""
        yield Static("", classes="frame-preview-title")
        if self._backend_type is not None:
            with Container(classes="frame-preview-canvas"):
                yield self._backend_type(id="frame_preview_image")
        else:
            yield Static(
                "Inline raster graphics are unavailable in this terminal. "
                "Press O to open the original image in your default viewer.",
                classes="frame-preview-fallback",
            )

    def show_frame(self, path: str, frame_number: int, score: float) -> bool:
        """Show an original frame, scaled only by the raster display backend."""
        image_path = Path(path).expanduser()
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Frame image is no longer available: {image_path}"
            )

        self.current_path = image_path
        self.display = True
        self.query_one(".frame-preview-title", Static).update(
            f"Frame {frame_number:,} · sharpness {score:.2f} · "
            "Press O to open"
        )

        if self._backend_type is None:
            return False

        raster_widget = self.query_one("#frame_preview_image")
        raster_widget.image = image_path
        return True

    def clear(self) -> None:
        """Stop displaying a frame so deleted temp files are never re-opened.

        The raster backend keeps the image *path* and lazily re-opens it on
        every repaint. When the extraction temp directory is removed after a
        save, a stale path would crash Textual's render loop, so the reference
        must be dropped before that cleanup runs.
        """
        self.current_path = None
        self.display = False
        if self._backend_type is None:
            return
        try:
            raster_widget = self.query_one("#frame_preview_image")
        except NoMatches:
            return
        raster_widget.image = None
