from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

Point = tuple[float, float]


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, point: Point) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        and abs(_orientation(a, b, point)) <= 1e-9
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and (
        (o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)
    ):
        return True

    return (
        (abs(o1) <= 1e-9 and _on_segment(a, b, c))
        or (abs(o2) <= 1e-9 and _on_segment(a, b, d))
        or (abs(o3) <= 1e-9 and _on_segment(c, d, a))
        or (abs(o4) <= 1e-9 and _on_segment(c, d, b))
    )


def validate_polygon(points: Sequence[Point]) -> None:
    if len(points) < 3:
        raise ValueError("A zone polygon needs at least three points.")

    if any(
        not isfinite(x) or not isfinite(y) or x < 0 or x > 1 or y < 0 or y > 1
        for x, y in points
    ):
        raise ValueError("Zone coordinates must be finite values between 0 and 1.")

    if len(set(points)) != len(points):
        raise ValueError("Zone polygon points must be unique.")

    edge_count = len(points)
    for first in range(edge_count):
        a = points[first]
        b = points[(first + 1) % edge_count]
        for second in range(first + 1, edge_count):
            if second == first or second == (first + 1) % edge_count:
                continue
            if first == 0 and second == edge_count - 1:
                continue
            c = points[second]
            d = points[(second + 1) % edge_count]
            if _segments_intersect(a, b, c, d):
                raise ValueError("Zone polygon edges must not intersect.")

    area_twice = sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
    if abs(area_twice) <= 1e-9:
        raise ValueError("Zone polygon must enclose an area.")


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False

    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        if _on_segment(start, end, point):
            return True

        if (start[1] > y) != (end[1] > y):
            intersection_x = (
                (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1])
                + start[0]
            )
            if x < intersection_x:
                inside = not inside

    return inside


def bbox_iou(first: Sequence[float], second: Sequence[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(
        0.0, second[3] - second[1]
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0
