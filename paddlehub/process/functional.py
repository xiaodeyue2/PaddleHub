# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os

import cv2
import paddle
import matplotlib
import numpy as np
from pycocotools.coco import COCO
from PIL import Image, ImageEnhance
from matplotlib import pyplot as plt

matplotlib.use('Agg')


def normalize(im, mean, std):
    im = im.astype(np.float32, copy=False) / 255.0
    im -= mean
    im /= std
    return im


def permute(im):
    im = np.transpose(im, (2, 0, 1))
    return im


def resize(im, target_size=608, interp=cv2.INTER_LINEAR):
    if isinstance(target_size, list) or isinstance(target_size, tuple):
        w = target_size[0]
        h = target_size[1]
    else:
        w = target_size
        h = target_size
    im = cv2.resize(im, (w, h), interpolation=interp)
    return im


def resize_long(im, long_size=224, interpolation=cv2.INTER_LINEAR):
    value = max(im.shape[0], im.shape[1])
    scale = float(long_size) / float(value)
    resized_width = int(round(im.shape[1] * scale))
    resized_height = int(round(im.shape[0] * scale))

    im = cv2.resize(im, (resized_width, resized_height), interpolation=interpolation)
    return im


def horizontal_flip(im):
    if len(im.shape) == 3:
        im = im[:, ::-1, :]
    elif len(im.shape) == 2:
        im = im[:, ::-1]
    return im


def vertical_flip(im):
    if len(im.shape) == 3:
        im = im[::-1, :, :]
    elif len(im.shape) == 2:
        im = im[::-1, :]
    return im


def brightness(im, brightness_lower, brightness_upper):
    brightness_delta = np.random.uniform(brightness_lower, brightness_upper)
    im = ImageEnhance.Brightness(im).enhance(brightness_delta)
    return im


def contrast(im, contrast_lower, contrast_upper):
    contrast_delta = np.random.uniform(contrast_lower, contrast_upper)
    im = ImageEnhance.Contrast(im).enhance(contrast_delta)
    return im


def saturation(im, saturation_lower, saturation_upper):
    saturation_delta = np.random.uniform(saturation_lower, saturation_upper)
    im = ImageEnhance.Color(im).enhance(saturation_delta)
    return im


def hue(im, hue_lower, hue_upper):
    hue_delta = np.random.uniform(hue_lower, hue_upper)
    im = np.array(im.convert('HSV'))
    im[:, :, 0] = im[:, :, 0] + hue_delta
    im = Image.fromarray(im, mode='HSV').convert('RGB')
    return im


def rotate(im, rotate_lower, rotate_upper):
    rotate_delta = np.random.uniform(rotate_lower, rotate_upper)
    im = im.rotate(int(rotate_delta))
    return im


def is_image_file(filename: str) -> bool:
    '''Determine whether the input file name is a valid image file name.'''
    ext = os.path.splitext(filename)[-1].lower()
    return ext in ['.bmp', '.dib', '.png', '.jpg', '.jpeg', '.pbm', '.pgm', '.ppm', '.tif', '.tiff']


def get_img_file(dir_name: str) -> list:
    '''Get all image file paths in several directories which have the same parent directory.'''
    images = []
    for parent, dirnames, filenames in os.walk(dir_name):
        for filename in filenames:
            if not is_image_file(filename):
                continue
            img_path = os.path.join(parent, filename)
            images.append(img_path)
    images.sort()
    return images


def box_crop(boxes: np.ndarray, labels: np.ndarray, scores: np.ndarray, crop: list, img_shape: list):
    """Crop the boxes ,labels, scores according to the given shape"""

    x, y, w, h = map(float, crop)
    im_w, im_h = map(float, img_shape)

    boxes = boxes.copy()
    boxes[:, 0], boxes[:, 2] = (boxes[:, 0] - boxes[:, 2] / 2) * im_w, (boxes[:, 0] + boxes[:, 2] / 2) * im_w
    boxes[:, 1], boxes[:, 3] = (boxes[:, 1] - boxes[:, 3] / 2) * im_h, (boxes[:, 1] + boxes[:, 3] / 2) * im_h

    crop_box = np.array([x, y, x + w, y + h])
    centers = (boxes[:, :2] + boxes[:, 2:]) / 2.0
    mask = np.logical_and(crop_box[:2] <= centers, centers <= crop_box[2:]).all(axis=1)

    boxes[:, :2] = np.maximum(boxes[:, :2], crop_box[:2])
    boxes[:, 2:] = np.minimum(boxes[:, 2:], crop_box[2:])
    boxes[:, :2] -= crop_box[:2]
    boxes[:, 2:] -= crop_box[:2]

    mask = np.logical_and(mask, (boxes[:, :2] < boxes[:, 2:]).all(axis=1))
    boxes = boxes * np.expand_dims(mask.astype('float32'), axis=1)
    labels = labels * mask.astype('float32')
    scores = scores * mask.astype('float32')
    boxes[:, 0], boxes[:, 2] = (boxes[:, 0] + boxes[:, 2]) / 2 / w, (boxes[:, 2] - boxes[:, 0]) / w
    boxes[:, 1], boxes[:, 3] = (boxes[:, 1] + boxes[:, 3]) / 2 / h, (boxes[:, 3] - boxes[:, 1]) / h

    return boxes, labels, scores, mask.sum()


def box_iou_xywh(box1: np.ndarray, box2: np.ndarray) -> float:
    """Calculate iou by xywh"""

    assert box1.shape[-1] == 4, "Box1 shape[-1] should be 4."
    assert box2.shape[-1] == 4, "Box2 shape[-1] should be 4."

    b1_x1, b1_x2 = box1[:, 0] - box1[:, 2] / 2, box1[:, 0] + box1[:, 2] / 2
    b1_y1, b1_y2 = box1[:, 1] - box1[:, 3] / 2, box1[:, 1] + box1[:, 3] / 2
    b2_x1, b2_x2 = box2[:, 0] - box2[:, 2] / 2, box2[:, 0] + box2[:, 2] / 2
    b2_y1, b2_y2 = box2[:, 1] - box2[:, 3] / 2, box2[:, 1] + box2[:, 3] / 2

    inter_x1 = np.maximum(b1_x1, b2_x1)
    inter_x2 = np.minimum(b1_x2, b2_x2)
    inter_y1 = np.maximum(b1_y1, b2_y1)
    inter_y2 = np.minimum(b1_y2, b2_y2)
    inter_w = inter_x2 - inter_x1
    inter_h = inter_y2 - inter_y1
    inter_w[inter_w < 0] = 0
    inter_h[inter_h < 0] = 0

    inter_area = inter_w * inter_h
    b1_area = (b1_x2 - b1_x1) * (b1_y2 - b1_y1)
    b2_area = (b2_x2 - b2_x1) * (b2_y2 - b2_y1)

    return inter_area / (b1_area + b2_area - inter_area)


def draw_boxes_on_image(image_path: str,
                        boxes: np.ndarray,
                        scores: np.ndarray,
                        labels: np.ndarray,
                        label_names: list,
                        score_thresh: float = 0.5):
    """Draw boxes on images."""
    image = np.array(Image.open(image_path))
    plt.figure()
    _, ax = plt.subplots(1)
    ax.imshow(image)

    image_name = image_path.split('/')[-1]
    print("Image {} detect: ".format(image_name))
    colors = {}
    for box, score, label in zip(boxes, scores, labels):
        if score < score_thresh:
            continue
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        label = int(label)
        if label not in colors:
            colors[label] = plt.get_cmap('hsv')(label / len(label_names))
        x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
        rect = plt.Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, linewidth=2.0, edgecolor=colors[label])
        ax.add_patch(rect)
        ax.text(x1,
                y1,
                '{} {:.4f}'.format(label_names[label], score),
                verticalalignment='bottom',
                horizontalalignment='left',
                bbox={
                    'facecolor': colors[label],
                    'alpha': 0.5,
                    'pad': 0
                },
                fontsize=8,
                color='white')
        print("\t {:15s} at {:25} score: {:.5f}".format(label_names[int(label)], str(list(map(int, list(box)))), score))
    image_name = image_name.replace('jpg', 'png')
    plt.axis('off')
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())
    plt.savefig("./output/{}".format(image_name), bbox_inches='tight', pad_inches=0.0)
    print("Detect result save at ./output/{}\n".format(image_name))
    plt.cla()
    plt.close('all')


def img_shape(img_path: str):
    """Get image shape."""
    im = cv2.imread(img_path)
    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    h, w, c = im.shape
    return h, w, c


def get_label_infos(file_list: str):
    """Get label names by corresponding category ids."""
    map_label = COCO(file_list)
    label_names = []
    categories = map_label.loadCats(map_label.getCatIds())
    for category in categories:
        label_names.append(category['name'])
    return label_names


def subtract_imagenet_mean_batch(batch: paddle.Tensor) -> paddle.Tensor:
    """Subtract ImageNet mean pixel-wise from a BGR image."""
    mean = np.zeros(shape=batch.shape, dtype='float32')
    mean[:, 0, :, :] = 103.939
    mean[:, 1, :, :] = 116.779
    mean[:, 2, :, :] = 123.680
    mean = paddle.to_tensor(mean)
    return batch - mean


def gram_matrix(data: paddle.Tensor) -> paddle.Tensor:
    """Get gram matrix"""
    b, ch, h, w = data.shape
    features = data.reshape((b, ch, w * h))
    features_t = features.transpose((0, 2, 1))
    gram = features.bmm(features_t) / (ch * h * w)
    return gram
