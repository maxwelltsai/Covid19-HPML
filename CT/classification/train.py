import os
import numpy as np
import time
import pdb

from tensorboardX import SummaryWriter
import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F

import utils


def train_model(model, train_loader, epoch, num_epochs, optimizer, writer,
                current_lr, log_every=100):
    n_classes = model.n_classes
    metric = torch.nn.CrossEntropyLoss()

    y_probs = np.zeros((0, n_classes), np.float)
    y_trues = np.zeros((0), np.int)
    losses = []
    model.train()

    for i, (image, label) in enumerate(train_loader):
        optimizer.zero_grad()
        if torch.cuda.is_available():
            image = image.cuda()
            label = label.cuda()

        prediction = model.forward(image.float())
        loss = metric(prediction, label.long())
        loss.backward()
        optimizer.step()

        loss_value = loss.item()
        losses.append(loss_value)
        y_prob = F.softmax(prediction, dim=1)
        y_probs = np.concatenate([y_probs, y_prob.detach().cpu().numpy()])
        y_trues = np.concatenate([y_trues, label.cpu().numpy()])

    metric_collects = utils.calc_multi_cls_measures(y_probs, y_trues)

    train_loss_epoch = np.round(np.mean(losses), 4)
    return train_loss_epoch, metric_collects


def evaluate_model(model, val_loader, epoch, num_epochs, writer, current_lr,
                   log_every=20):
    n_classes = model.n_classes
    metric = torch.nn.CrossEntropyLoss()

    model.eval()
    for m in model.modules():
        if isinstance(m, nn.BatchNorm2d):
            m.train()
            m.weight.requires_grad = False
            m.bias.requires_grad = False

    y_probs = np.zeros((0, n_classes), np.float)
    y_trues = np.zeros((0), np.int)
    losses = []

    for i, (image, label) in enumerate(val_loader):

        if torch.cuda.is_available():
            image = image.cuda()
            label = label.cuda()

        prediction = model.forward(image.float())
        loss = metric(prediction, label.long())

        loss_value = loss.item()
        losses.append(loss_value)
        y_prob = F.softmax(prediction, dim=1)
        y_probs = np.concatenate([y_probs, y_prob.detach().cpu().numpy()])
        y_trues = np.concatenate([y_trues, label.cpu().numpy()])

    metric_collects = utils.calc_multi_cls_measures(y_probs, y_trues)

    val_loss_epoch = np.round(np.mean(losses), 4)
    return val_loss_epoch, metric_collects