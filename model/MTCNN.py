from mtcnn_pytorch.src.get_nets import PNet, RNet, ONet

# from PIL import Image
import cv2
import numpy as np
import torch
from torch.autograd import Variable
from mtcnn_pytorch.src.get_nets import PNet, RNet, ONet
from mtcnn_pytorch.src.box_utils import nms, calibrate_box, get_image_boxes, convert_to_square
from mtcnn_pytorch.src.first_stage import run_first_stage

import pdb
"""
updated original MTCNN a little, removed unneeded landmarks calculation
original from https://github.com/TropComplique/mtcnn-pytorch
"""

class MTCNN():
    def __init__(self):
        self.pnet = PNet()
        self.rnet = RNet()
        self.onet = ONet()
        self.onet.eval()
#         self.nets = (self.pnet,self.rnet,self.onet)

    def detect_faces(self,image, min_face_size=180.0,
                 thresholds=[0.6, 0.7, 0.8],
                 nms_thresholds=[0.7, 0.7, 0.7]):
        """
        Arguments:
            image: an instance of PIL.Image.
            min_face_size: a float number.
            thresholds: a list of length 3.
            nms_thresholds: a list of length 3.

        Returns:
            two float numpy arrays of shapes [n_boxes, 4] and [n_boxes, 10],
            bounding boxes and facial landmarks.
        """

        # BUILD AN IMAGE PYRAMID
        width, height = image.size
        min_length = min(height, width)

        min_detection_size = 12
        factor = 0.707  # sqrt(0.5)

        # scales for scaling the image
        scales = []

        # scales the image so that
        # minimum size that we can detect equals to
        # minimum face size that we want to detect
        m = min_detection_size/min_face_size
        min_length *= m

        factor_count = 0
        torch.set_grad_enabled(False)
        while min_length > min_detection_size:
            scales.append(m*factor**factor_count)
            min_length *= factor
            factor_count += 1

        # STAGE 1

        # it will be returned
        bounding_boxes = []

        # run P-Net on different scales
        for s in scales:
            boxes = run_first_stage(image, self.pnet, scale=s, threshold=thresholds[0])
            bounding_boxes.append(boxes)

        # collect boxes (and offsets, and scores) from different scales
        bounding_boxes = [i for i in bounding_boxes if i is not None]
        if bounding_boxes == []:
            return []
        bounding_boxes = np.vstack(bounding_boxes)

        keep = nms(bounding_boxes[:, 0:5], nms_thresholds[0])
        bounding_boxes = bounding_boxes[keep]

        # use offsets predicted by self.pnet to transform bounding boxes
        bounding_boxes = calibrate_box(bounding_boxes[:, 0:5], bounding_boxes[:, 5:])
        # shape [n_boxes, 5]

        bounding_boxes = convert_to_square(bounding_boxes)
        bounding_boxes[:, 0:4] = np.round(bounding_boxes[:, 0:4])

        # STAGE 2

        img_boxes = get_image_boxes(bounding_boxes, image, size=24)
        img_boxes = Variable(torch.FloatTensor(img_boxes))
        output = self.rnet(img_boxes)
        offsets = output[0].data.numpy()  # shape [n_boxes, 4]
        probs = output[1].data.numpy()  # shape [n_boxes, 2]

        keep = np.where(probs[:, 1] > thresholds[1])[0]
        bounding_boxes = bounding_boxes[keep]
        bounding_boxes[:, 4] = probs[keep, 1].reshape((-1,))
        offsets = offsets[keep]

        keep = nms(bounding_boxes, nms_thresholds[1])
        bounding_boxes = bounding_boxes[keep]
        bounding_boxes = calibrate_box(bounding_boxes, offsets[keep])
        bounding_boxes = convert_to_square(bounding_boxes)
        bounding_boxes[:, 0:4] = np.round(bounding_boxes[:, 0:4])

        # STAGE 3

        img_boxes = get_image_boxes(bounding_boxes, image, size=48)
        if len(img_boxes) == 0: 
            return []
        img_boxes = Variable(torch.FloatTensor(img_boxes))
        output = self.onet(img_boxes)
        offsets = output[1].data.numpy()  # shape [n_boxes, 4]
        probs = output[2].data.numpy()  # shape [n_boxes, 2]

        keep = np.where(probs[:, 1] > thresholds[2])[0]
        bounding_boxes = bounding_boxes[keep]
        bounding_boxes[:, 4] = probs[keep, 1].reshape((-1,))
        offsets = offsets[keep]

        bounding_boxes = calibrate_box(bounding_boxes, offsets)
        keep = nms(bounding_boxes, nms_thresholds[2], mode='min')
        bounding_boxes = bounding_boxes[keep]
        
#         img = image.crop(bounding_boxes[0][:-1].tolist())
        
        return bounding_boxes       
         
