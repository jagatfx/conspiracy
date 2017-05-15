import json
import random
import numpy as np
from glob import glob
from PIL import Image, ImageDraw
from faces import compare_faces
from itertools import chain
from images import util, layout, compare, annotate

SAMPLE = 200
SIZE = (1400, 800)
MAX_SIZE = (0.3, 0.3)
MAX_SIZE = (MAX_SIZE[0]*SIZE[0], MAX_SIZE[1]*SIZE[1])
images = random.sample(glob('../reality/data/_images/*'), SAMPLE)



def load_images(impath, type):
    """load images given a parent image path"""
    imid = impath.split('/')[-1]
    dir = 'data/{}/{}'.format(type, imid)
    try:
        bboxes = json.load(open('{}/bboxes.json'.format(dir), 'r'))
        crops = glob('{}/*.jpg'.format(dir))
        return [{
            'path': c,
            'bbox': b,
            'imid': imid,
            'impath': impath
        } for c, b in zip(crops, bboxes)]
    except FileNotFoundError:
        return []


def filter_pairs(pairs, images):
    """filters redundant image pairs"""
    # remove permutations
    pairs = set(tuple(sorted(p)) for p in pairs)

    # filter out self-pairings
    # filter out pairs that are between two of the same images
    # filter out pairs that are from really similar images
    pairs = [(a, b) for a, b in pairs
             if a != b
             and images[a]['imid'] != images[b]['imid']
             and compare.compute_dist(images[a]['impath'], images[b]['impath']) > 0.5] # TODO adjust this thresh
    return pairs


def get_similar(images, thresh, comparator, prefix=None):
    """get pairs of similar images,
    according to the comparator (distance) function"""
    dists = comparator([i['path'] for i in images])
    pairs = np.argwhere(dists <= thresh)
    pairs = filter_pairs(pairs, images)

    # get unique dist mat indices
    indices = set(chain(*pairs))
    images = {idx: images[idx] for idx in indices}

    if prefix is not None:
        # since indices can collide, add prefixes
        pairs = [
            ('{}{}'.format(prefix, a), '{}{}'.format(prefix, b))
            for a, b in pairs]
        images = {'{}{}'.format(prefix, k): v for k, v in images.items()}
    return pairs, images


def prepare_images(images):
    """prepare images by loading and scaling them,
    scaling their bounding boxes accordingly"""
    for image in images.values():
        im = Image.open(image['impath'])
        xo, yo = im.size

        im = util.resize_to_limit(im, MAX_SIZE)
        xn, yn = im.size

        resize_ratio = (xn/xo, yn/yo)

        # scale bbox accordingly
        image['bbox'] = util.scale_rect(image['bbox'], resize_ratio)
        image['image'] = im
    return images


def render(images, pairs, out='output.jpg', shakiness=30):
    """collages the images, annotating similar pairs by drawing links"""
    canvas = Image.new('RGB', SIZE, color=0)
    draw = ImageDraw.Draw(canvas)

    # layout images
    # this doesn't guarantee that every image will be included!
    packed = layout.pack([im['image'] for im in images.values()], canvas)
    for im, pos in zip(images.values(), packed):
        pos = (
            round(pos[0] + util.noise(shakiness)),
            round(pos[1] + util.noise(shakiness)))
        canvas.paste(im['image'], pos)
        im['bbox'] = util.shift_rect(im['bbox'], pos)

    # draw circles
    for im in images.values():
        annotate.circle(draw, im['bbox'])

    # draw links
    for a, b in pairs:
        annotate.link(draw, images[a]['bbox'][:2], images[b]['bbox'][:2])
    canvas.save(out)


if __name__ == '__main__':
    FACE_DIST_THRESH = 0.4

    faces, objects = [], []
    for path in images:
        faces.extend(load_images(path, 'faces'))
        objects.extend(load_images(path, 'objects'))

    print('faces:', len(faces))
    print('objects:', len(objects))
    fpairs, faces = get_similar(faces, FACE_DIST_THRESH, compare_faces, prefix='f')
    print('faces:', len(faces))
    opairs, objects = get_similar(objects, 2, compare.compute_dists, prefix='o')
    print('objects:', len(objects))

    pairs = fpairs + opairs
    images = {**faces, **objects}

    if pairs:
        print(pairs)
        images = prepare_images(images)
        render(images, pairs, out='output.jpg')