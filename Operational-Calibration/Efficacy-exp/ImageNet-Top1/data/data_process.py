import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.distributed as dist
import torch.optim
import torch.multiprocessing as mp
import torch.utils.data
import torch.utils.data.distributed
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models
import torchvision

from torch.nn import functional as F
import PIL

import os
import shutil
import time
import random

import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torch.utils.data as data
import torchvision.transforms as transforms
import torchvision.datasets as datasets
from torch.nn import functional as F

from utils import Bar, Logger, AverageMeter, accuracy, mkdir_p, savefig

import numpy as np
import matplotlib.pyplot as plt

np.random.seed(1)
seed = 1
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)


os.environ['CUDA_VISIBLE_DEVICES'] = '6,7,8,9'
use_cuda = torch.cuda.is_available()


class Net(nn.Module):

    def __init__(self):
        super(Net, self).__init__()
        # Convolution (In LeNet-5, 32x32 images are given as input. Hence
        # padding of 2 is done below)
        self.BackBone = BackBone

    def forward(self, x):
        return self.BackBone(x)

    def hidden(self, x):
        for name, midlayer in self.BackBone._modules.items():
            if name != 'fc':
                x = midlayer(x)
            else:
                break
        x = torch.squeeze(x)
        return x


    def hidden(self, x):
        x_ch0 = torch.unsqueeze(x[:, 0], 1) * \
                                    (0.229 / 0.5) + (0.485 - 0.5) / 0.5
        x_ch1 = torch.unsqueeze(x[:, 1], 1) * \
                                    (0.224 / 0.5) + (0.456 - 0.5) / 0.5
        x_ch2 = torch.unsqueeze(x[:, 2], 1) * \
                                    (0.225 / 0.5) + (0.406 - 0.5) / 0.5
        x = torch.cat((x_ch0, x_ch1, x_ch2), 1)
            # N x 3 x 299 x 299
        x = self.BackBone.Conv2d_1a_3x3(x)
            # N x 32 x 149 x 149
        x = self.BackBone.Conv2d_2a_3x3(x)
            # N x 32 x 147 x 147
        x = self.BackBone.Conv2d_2b_3x3(x)
            # N x 64 x 147 x 147
        x = F.max_pool2d(x, kernel_size=3, stride=2)
            # N x 64 x 73 x 73
        x = self.BackBone.Conv2d_3b_1x1(x)
            # N x 80 x 73 x 73
        x = self.BackBone.Conv2d_4a_3x3(x)
            # N x 192 x 71 x 71
        x = F.max_pool2d(x, kernel_size=3, stride=2)
            # N x 192 x 35 x 35
        x = self.BackBone.Mixed_5b(x)
            # N x 256 x 35 x 35
        x = self.BackBone.Mixed_5c(x)
            # N x 288 x 35 x 35
        x = self.BackBone.Mixed_5d(x)
            # N x 288 x 35 x 35
        x = self.BackBone.Mixed_6a(x)
            # N x 768 x 17 x 17
        x = self.BackBone.Mixed_6b(x)
            # N x 768 x 17 x 17
        x = self.BackBone.Mixed_6c(x)
            # N x 768 x 17 x 17
        x = self.BackBone.Mixed_6d(x)
            # N x 768 x 17 x 17
        x = self.BackBone.Mixed_6e(x)
            # N x 768 x 17 x 17
        x = self.BackBone.Mixed_7a(x)
            # N x 1280 x 8 x 8
        x = self.BackBone.Mixed_7b(x)
            # N x 2048 x 8 x 8
        x = self.BackBone.Mixed_7c(x)
            # N x 2048 x 8 x 8
            # Adaptive average pooling
        x = F.adaptive_avg_pool2d(x, (1, 1))
            # N x 2048 x 1 x 1
        x = x.view(x.size(0), -1)
        return x


def test(val_loader, model, criterion, use_cuda):
    global best_acc

    batch_time = AverageMeter()
    data_time = AverageMeter()
    losses = AverageMeter()
    top1 = AverageMeter()
    top5 = AverageMeter()

    # switch to evaluate mode
    model.eval()

    end = time.time()
    bar = Bar('Processing', max=len(val_loader))
    correct = 0
    for batch_idx, (inputs, targets) in enumerate(val_loader):
        # measure data loading time
        data_time.update(time.time() - end)

        if use_cuda:
            inputs, targets = inputs.cuda(), targets.cuda()
        inputs, targets = torch.autograd.Variable(
            inputs, volatile=True), torch.autograd.Variable(targets)

        # compute output
        # outputs = model(inputs)
        outputs = model.hidden(inputs)
        outputs = model.BackBone.fc(outputs)

        _, pred = torch.max(outputs,1)
        correct += (pred == targets).sum().item()
        loss = criterion(outputs, targets)

        # measure accuracy and record loss
        prec1, prec5 = accuracy(outputs.data, targets.data, topk=(1, 5))
        losses.update(loss.item(), inputs.size(0))
        top1.update(prec1.item(), inputs.size(0))
        top5.update(prec5.item(), inputs.size(0))

        # measure elapsed time
        batch_time.update(time.time() - end)
        end = time.time()

        # plot progress
        bar.suffix = '({batch}/{size}) Data: {data:.3f}s | Batch: {bt:.3f}s | Total: {total:} | ETA: {eta:} | Loss: {loss:.4f} | top1: {top1: .4f} | top5: {top5: .4f}'.format(
            batch=batch_idx + 1,
            size=len(val_loader),
            data=data_time.avg,
            bt=batch_time.avg,
            total=bar.elapsed_td,
            eta=bar.eta_td,
            loss=losses.avg,
            top1=top1.avg,
            top5=top5.avg,
        )
        bar.next()
    bar.finish()
    return (losses.avg, top1.avg)


def save_fc(val_loader, model):
    fc_output = np.array([])
    y = np.array([])
    correct = 0
    model.eval()
    for batch_idx, (inputs, targets) in enumerate(val_loader):
        inputs, targets = inputs.cuda(), targets.cuda()
        temp_output = model.hidden(inputs)
        pred = model.BackBone.fc(temp_output)
        _, pred = torch.max(pred, 1)
        correct += (pred == targets).sum().item()

        fc_output = np.append(fc_output, temp_output.cpu().detach().numpy())
        y = np.append(y, targets.cpu().detach().numpy())
        if batch_idx >= 1000:
            break
    fc_output = fc_output.reshape(-1, 2048)
    y = y.reshape(-1)
    ind = np.random.permutation(fc_output.shape[0])
    divide = 5000
    torch.save(tuple([fc_output[0:divide], y[0:divide]]), 'operational.pt')
    torch.save(tuple([fc_output[divide:], y[divide:]]), 'test.pt')
    fc_output = torch.Tensor(fc_output[0:divide]).cuda()
    y = torch.Tensor(y[0:divide]).long().cuda()
    pred = model.BackBone.fc(fc_output)
    _, pred = torch.max(pred, 1)
    correct = (pred == y).sum().item()
    print(correct * 1.0 / pred.shape[0])
    

def test_fc(model):
    fc_output, y = torch.load('operational.pt')
    fc_output = torch.Tensor(fc_output)
    y = torch.LongTensor(y)
    fc_output, y = fc_output.cuda(), y.cuda()
    pred = model.BackBone.fc(fc_output)
    softmaxes = F.softmax(pred, dim=1)
    conf, pred = torch.max(softmaxes, 1)
    correct = (pred == y).sum().item()
    print('acc is {}'. format(1.0 * correct / pred.shape[0]))
    conf = conf.cpu().detach().numpy()
    pred = pred.cpu().detach().numpy()
    y = y.cpu().detach().numpy()
    index = np.where(pred != y)
    print('high conf mis is {}'.format(np.sum(conf[index] > 0.9)))
    print('high conf is {}'.format(np.sum(conf>0.9)))   
    #index1 = np.where(y == pred)[0]
    #index2 = np.where(y != pred)[0]
    #from sklearn.manifold import TSNE
    #x_embedded = TSNE(n_components=2).fit_transform(fc_output.cpu().detach().numpy())
    #plt.scatter(x_embedded[index1,0], x_embedded[index1,1], c='r', marker='o')
    #plt.scatter(x_embedded[index2,0], x_embedded[index2,1], c='b', marker='+')
    #plt.savefig('fig.pdf', format='pdf',dpi=1000)

normalize = transforms.Normalize(mean=[0.485, 0.456, 0.405],
                                 std=[0.229, 0.224, 0.225])

transforms = transforms.Compose([
    transforms.Resize(136),
#    transforms.RandomRotation(30),
#    transforms.RandomAffine(0, (0.5,0.5)),   
#    transforms.Resize(256),
    transforms.Pad(padding=120, padding_mode='edge'),
    transforms.CenterCrop(299),
    transforms.ToTensor(),
    normalize,
])


imagenet_data = torchvision.datasets.ImageNet(
    'val-data/', split='val', download=True, transform=transforms)

val_loader = torch.utils.data.DataLoader(imagenet_data,
                                         batch_size=10, shuffle=True,
                                         num_workers=4)


BackBone = torchvision.models.inception_v3(pretrained=True, transform_input=True)
# BackBone = torchvision.models.resnet152(pretrained=True)
net = Net()
# net = torchvision.models.resnet101(pretrained=True)
net.cuda()
# net = torch.nn.parallel.DistributedDataParallel(net)
criterion = nn.CrossEntropyLoss()
# test_loss, test_acc = test(val_loader, net, criterion, use_cuda=True)
save_fc(val_loader, net)
test_fc(net)
