import cv2

def get_foot_position(bbox):
    x1, y1, x2, y2 = bbox 
    return int((x1 + x2)/ 2), int(y2)