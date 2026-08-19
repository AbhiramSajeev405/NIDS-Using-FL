import torch
import torch.nn as nn
import torch.nn.functional as F

class CNNModel(nn.Module):
    def __init__(self, input_dim, num_classes=2):
        super(CNNModel, self).__init__()
        # 1D CNN expects input of shape (batch, channels, length)
        # We will reshape (batch, features) to (batch, 1, features) in forward pass
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)

        # Pooling will halve the dimension each time
        self.pool = nn.MaxPool1d(2)

        # Calculate flattened size dynamically to avoid mismatch with any input_dim
        # Use a parameter's device to ensure dummy tensor is on the same device
        with torch.no_grad():
            param_device = self.conv1.weight.device
            dummy = torch.zeros(1, 1, input_dim, device=param_device)
            dummy = self.pool(F.relu(self.conv1(dummy)))
            dummy = self.pool(F.relu(self.conv2(dummy)))
            linear_input_size = dummy.view(1, -1).shape[1]

        self.fc1 = nn.Linear(linear_input_size, 128)
        self.fc2 = nn.Linear(128, num_classes)
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        # x shape: (batch_size, input_dim) -> reshape to (batch_size, 1, input_dim)
        x = x.unsqueeze(1)

        x = F.relu(self.conv1(x))
        x = self.pool(x)

        x = F.relu(self.conv2(x))
        x = self.pool(x)

        # Flatten
        x = x.view(x.size(0), -1)

        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x
