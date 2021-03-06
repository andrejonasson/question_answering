""" CS224n, altered with big bug fix """

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gzip
import os
import re
import tarfile
import argparse
from os.path import join as pjoin
from six.moves import urllib

from tensorflow import gfile
from tqdm import tqdm
import numpy as np

from squad_preprocess import tokenize

_PAD = "<pad>"
_SOS = "<sos>"
_UNK = "<unk>"
_START_VOCAB = [_PAD, _SOS, _UNK]

PAD_ID = 0
SOS_ID = 1
UNK_ID = 2

def setup_args():
    parser = argparse.ArgumentParser()
    code_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)))
    vocab_dir = os.path.join(code_dir, "..", "..", "data", "squad")
    glove_dir = os.path.join(code_dir, "..", "..", "download", "dwr")
    source_dir = os.path.join(code_dir, "..", "..", "data", "squad")
    parser.add_argument("--source_dir", default=source_dir)
    parser.add_argument("--glove_dir", default=glove_dir)
    parser.add_argument("--vocab_dir", default=vocab_dir)
    parser.add_argument("--glove_dim", default=100, type=int)
    parser.add_argument("--random_init", default=True, type=bool)
    parser.add_argument("--glove_source", choices=['wiki', 'crawl_cs', 'crawl_ci'])  # added for use with different glove sources
    return parser.parse_args()


def basic_tokenizer(sentence):
    words = []
    for space_separated_fragment in sentence.strip().split():
        words.extend(re.split(" ", space_separated_fragment.decode('utf-8')))
    return [w for w in words if w]


def initialize_vocabulary(vocabulary_path):
    # map vocab to word embeddings
    if gfile.Exists(vocabulary_path):
        rev_vocab = []
        with gfile.GFile(vocabulary_path, mode="r") as f:
            rev_vocab.extend(f.readlines())
        rev_vocab = [line.strip('\n') for line in rev_vocab]
        vocab = dict([(x, y) for (y, x) in enumerate(rev_vocab)])
        return vocab, rev_vocab
    else:
        raise ValueError("Vocabulary file %s not found.", vocabulary_path)


def process_glove(args, vocab_list, save_path, size=4e5, random_init=True):
    """
    :param vocab_list: [vocab]
    :return:

    NOTE: bug fixed in Stanfords CS224n squad code which had if if if instead of if elif elif
    """
    if not gfile.Exists(save_path + ".npz"):
        if args.glove_source == 'wiki':
            glove_path = os.path.join(args.glove_dir, "glove.6B.{}d.txt".format(args.glove_dim))
        elif args.glove_source == 'crawl_cs':
            glove_path = os.path.join(args.glove_dir, "glove.840B.300d.txt")
            args.glove_dim = 300
        elif args.glove_source == 'crawl_ci':
            glove_path = os.path.join(args.glove_dir, "glove.42B.300d.txt")
            args.glove_dim = 300
        
        if random_init:
            glove = np.random.randn(len(vocab_list), args.glove_dim)
        else:
            glove = np.zeros((len(vocab_list), args.glove_dim))
        found = 0
        with open(glove_path, 'r', encoding='utf8') as fh:  # NOTE: encoding='utf8, new addition, may cause problems elsewhere
            for line in tqdm(fh, total=size):
                array = line.lstrip().rstrip().split(" ")
                word = array[0]
                vector = list(map(float, array[1:]))
                if word in vocab_list:
                    idx = vocab_list.index(word)
                    glove[idx, :] = vector
                    found += 1
                elif word.capitalize() in vocab_list:
                    idx = vocab_list.index(word.capitalize())
                    glove[idx, :] = vector
                    found += 1
                elif word.lower() in vocab_list:
                    idx = vocab_list.index(word.lower())
                    glove[idx, :] = vector
                    found += 1
                elif word.upper() in vocab_list:
                    idx = vocab_list.index(word.upper())
                    glove[idx, :] = vector
                    found += 1

        print("{}/{} of word vocab have corresponding vectors in {}".format(found, len(vocab_list), glove_path))
        np.savez_compressed(save_path, glove=glove)
        print("saved trimmed glove matrix at: {}".format(save_path))


def create_vocabulary(vocabulary_path, data_paths, tokenizer):
    if not gfile.Exists(vocabulary_path):
        print("Creating vocabulary %s from data %s" % (vocabulary_path, str(data_paths)))
        vocab = {}
        for path in data_paths:
            with open(path, mode="rb") as f:
                counter = 0
                for line in f:
                    counter += 1
                    if counter % 100000 == 0:
                        print("processing line %d" % counter)
                    tokens = tokenizer(line)
                    for w in tokens:
                        if w in vocab:
                            vocab[w] += 1
                        else:
                            vocab[w] = 1
        vocab_list = _START_VOCAB + sorted(vocab, key=vocab.get, reverse=True)
        print("Vocabulary size: %d" % len(vocab_list))
        with gfile.GFile(vocabulary_path, mode="wb") as vocab_file:
            for w in vocab_list:
                vocab_file.write(w + "\n")


def sentence_to_token_ids(sentence, vocabulary, tokenizer):
    words = tokenizer(sentence)
    return [vocabulary.get(w, UNK_ID) for w in words]


def data_to_token_ids(data_path, target_path, vocabulary_path,
                      tokenizer):
    if not gfile.Exists(target_path):
        print("Tokenizing data in %s" % data_path)
        vocab, _ = initialize_vocabulary(vocabulary_path)
        with gfile.GFile(data_path, mode="rb") as data_file:
            with gfile.GFile(target_path, mode="w") as tokens_file:
                counter = 0
                for line in data_file:
                    counter += 1
                    if counter % 5000 == 0:
                        print("tokenizing line %d" % counter)
                    token_ids = sentence_to_token_ids(line, vocab, tokenizer)
                    tokens_file.write(" ".join([str(tok) for tok in token_ids]) + "\n")


if __name__ == '__main__':
    args = setup_args()
    vocab_path = pjoin(args.vocab_dir, "vocab.dat")

    train_path = pjoin(args.source_dir, "train")
    valid_path = pjoin(args.source_dir, "val")
    dev_path = pjoin(args.source_dir, "dev")

    create_vocabulary(vocab_path,
                      [pjoin(args.source_dir, "train.context"),
                       pjoin(args.source_dir, "train.question"),
                       pjoin(args.source_dir, "val.context"),
                       pjoin(args.source_dir, "val.question")],
                       basic_tokenizer)
    vocab, rev_vocab = initialize_vocabulary(pjoin(args.vocab_dir, "vocab.dat"))

    # ======== Trim Distributed Word Representation =======
    # If you use other word representations, you should change the code below
    if 'crawl' in args.glove_source:
        args.glove_dim = 300
    process_glove(args, rev_vocab, args.source_dir + "/glove.trimmed.{}".format(args.glove_dim),
                  random_init=args.random_init)

    # ======== Creating Dataset =========
    # We created our data files seperately
    # If your model loads data differently (like in bulk)
    # You should change the below code

    x_train_dis_path = train_path + ".ids.context"
    y_train_ids_path = train_path + ".ids.question"
    data_to_token_ids(train_path + ".context", x_train_dis_path, vocab_path, basic_tokenizer)
    data_to_token_ids(train_path + ".question", y_train_ids_path, vocab_path, basic_tokenizer)

    x_dis_path = valid_path + ".ids.context"
    y_ids_path = valid_path + ".ids.question"
    data_to_token_ids(valid_path + ".context", x_dis_path, vocab_path, basic_tokenizer)
    data_to_token_ids(valid_path + ".question", y_ids_path, vocab_path, basic_tokenizer)