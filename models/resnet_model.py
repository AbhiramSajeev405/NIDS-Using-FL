import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualBlock(nn.Module):
    """A single residual block for tabular data."""

    def __init__(self, dim, dropout=0.3):
        super(ResidualBlock, self).__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.bn1 = nn.BatchNorm1d(dim)
        self.fc2 = nn.Linear(dim, dim)
        self.bn2 = nn.BatchNorm1d(dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        residual = x
        out = F.relu(self.bn1(self.fc1(x)))
        out = self.dropout(out)
        out = self.bn2(self.fc2(out))
        out += residual  # Skip connection
        out = F.relu(out)
        return out


class ResNetModel(nn.Module):
    """Tabular ResNet: FC layers with skip connections.

    Skip connections help prevent vanishing gradients in deeper networks
    and allow the model to learn identity mappings when extra depth isn't needed.
    """

    def __init__(self, input_dim, num_classes=2, hidden_dim=128, num_blocks=3):
        super(ResNetModel, self).__init__()
        # Project input to hidden dimension
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.bn_input = nn.BatchNorm1d(hidden_dim)

        # Stack of residual blocks
        self.blocks = nn.Sequential(
            *[ResidualBlock(hidden_dim) for _ in range(num_blocks)]
        )

        # Classification head
        self.fc_out = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        x = F.relu(self.bn_input(self.input_proj(x)))
        x = self.blocks(x)
        x = self.fc_out(x)
        return x
