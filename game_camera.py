"""Camera behaviour shared by every view that shows a map."""

from constants import BASE_VIEW_WIDTH, DEFAULT_CAMERA_ZOOM, SCROLL_MARGIN


def zoom_for_window(window, base_zoom=DEFAULT_CAMERA_ZOOM):
    """Room zooms are tuned for a BASE_VIEW_WIDTH-wide window."""
    return base_zoom * window.width / BASE_VIEW_WIDTH


def clamp_to_map(cam_x, cam_y, view_w, view_h, map_width, map_height):
    """Keep the camera inside the map."""
    if view_w >= map_width:
        cam_x = map_width / 2
    else:
        cam_x = max(view_w / 2, min(cam_x, map_width - view_w / 2))
    if view_h >= map_height:
        cam_y = map_height / 2
    else:
        cam_y = max(view_h / 2, min(cam_y, map_height - view_h / 2))
    return cam_x, cam_y


def follow(camera, window, target, map_width, map_height):
    """Scroll so the target stays SCROLL_MARGIN inside the view edges, then
    clamp to the map.
    """
    view_w = window.width / camera.zoom
    view_h = window.height / camera.zoom

    cam_x, cam_y = camera.position
    left, right = cam_x - view_w / 2, cam_x + view_w / 2
    bottom, top = cam_y - view_h / 2, cam_y + view_h / 2

    if target.center_x > right - SCROLL_MARGIN:
        cam_x += target.center_x - (right - SCROLL_MARGIN)
    if target.center_x < left + SCROLL_MARGIN:
        cam_x -= (left + SCROLL_MARGIN) - target.center_x
    if target.center_y > top - SCROLL_MARGIN:
        cam_y += target.center_y - (top - SCROLL_MARGIN)
    if target.center_y < bottom + SCROLL_MARGIN:
        cam_y -= (bottom + SCROLL_MARGIN) - target.center_y

    camera.position = clamp_to_map(cam_x, cam_y, view_w, view_h,
                                   map_width, map_height)


def snap_to(camera, window, x, y, map_width, map_height):
    """Jump the camera straight to a point, clamped to the map."""
    view_w = window.width / camera.zoom
    view_h = window.height / camera.zoom
    camera.position = clamp_to_map(x, y, view_w, view_h, map_width, map_height)
