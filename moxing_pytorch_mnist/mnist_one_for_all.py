# coding:utf-8

# Copyright 2018 Deep Learning Service of Huawei Cloud. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import moxing.pytorch as mox

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms

parser = argparse.ArgumentParser()
parser.add_argument('--data_url', type=str, default=None, help='s3 path of dataset')
parser.add_argument('--train_url', type=str, default=None, help='s3 path of outputs')
parser.add_argument('--batch_size', type=int, default=64, help='batch_size')

# Protect the arguments which are not parsed.
args, unparsed = parser.parse_known_args()


class Net(nn.Module):
  """ Network architecture. """

  def __init__(self):
    super(Net, self).__init__()
    self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
    self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
    self.conv2_drop = nn.Dropout2d()
    self.fc1 = nn.Linear(320, 50)
    self.fc2 = nn.Linear(50, 10)

  def forward(self, x):
    x = F.relu(F.max_pool2d(self.conv1(x), 2))
    x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
    x = x.view(-1, 320)
    x = F.relu(self.fc1(x))
    x = F.dropout(x, training=self.training)
    x = self.fc2(x)
    return F.log_softmax(x, dim=1)


def main():
  # Enable OBS access.
  mox.file.shift('os', 'mox')
  mox.dist.init_process_group()

  dataset = datasets.MNIST(
    args.data_url,
    train=True,
    download=False,
    transform=transforms.Compose([
      transforms.ToTensor(),
      transforms.Normalize((0.1307,), (0.3081,))
    ]))

  data_loader = mox.dist.AutoDataLoader(dataset, batch_size=args.batch_size)

  model = Net()
  model = mox.dist.AutoModule(model)

  optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.5)

  for epoch in range(10):
    epoch_loss = 0.0
    data_loader.set_epoch(epoch)
    for data, target in data_loader:
      optimizer.zero_grad()
      if torch.cuda_is_avaiable():
        target = target.cuda()
      output = model(data)
      loss = F.nll_loss(output, target)
      epoch_loss += loss.data
      loss.backward()
      optimizer.step()
    print('epoch ', epoch, ' : ', epoch_loss / len(data_loader))

  if args.train_url and mox.get_flag('rank') == 0:
    torch.save(model.state_dict(), args.train_url + 'model.pt')


if __name__ == "__main__":
  main()
