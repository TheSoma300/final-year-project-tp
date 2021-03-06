import torch.nn.functional as F
import torch.nn as nn

# Simple CNN
class CNN(nn.Module):
    def __init__(self, name, get_report_data=True):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=5, stride=2, padding=2)
        self.conv2 = nn.Conv2d(32, 16, kernel_size=5, stride=2, padding=2)

        self.fc1 = nn.Linear(16 * 8 * 24, 10)
        self.pool = F.max_pool2d
        
        if get_report_data:
          print('keeping log')
        
    def forward(self, x):
        x = x.unsqueeze(1)
        x = F.relu(self.pool(self.conv1(x), 2))
        x = F.relu(self.pool(self.conv2(x), 2))
        x = x.reshape(x.shape[0], -1)
        x = self.fc1(x)

        return F.softmax(x, dim=1)
