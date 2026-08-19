import torch
import torch.nn as nn


class LSTMModel(nn.Module):
    """Bidirectional LSTM for network traffic classification.

    Reshapes flat feature vector (batch, input_dim) into a pseudo-sequence
    (batch, seq_len, feature_dim) to leverage LSTM's temporal modelling.
    """

    def __init__(self, input_dim, num_classes=2, hidden_dim=64, num_layers=2, seq_len=4):
        super(LSTMModel, self).__init__()
        # Split input_dim into seq_len chunks
        # If input_dim=20 and seq_len=4, each step sees 5 features
        self.seq_len = seq_len
        self.feature_dim = (input_dim + seq_len - 1) // seq_len
        self.pad_size = (self.feature_dim * seq_len) - input_dim

        self.lstm = nn.LSTM(
            input_size=self.feature_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=0.3 if num_layers > 1 else 0.0,
        )
        # Bidirectional doubles the hidden dim
        self.fc1 = nn.Linear(hidden_dim * 2, 64)
        self.fc2 = nn.Linear(64, num_classes)
        self.dropout = nn.Dropout(0.3)
        self.relu = nn.ReLU()

    def forward(self, x):
        # x: (batch, input_dim) -> (batch, seq_len, feature_dim)
        if self.pad_size > 0:
            x = nn.functional.pad(x, (0, self.pad_size))
        x = x.view(x.size(0), self.seq_len, self.feature_dim)

        # LSTM output: (batch, seq_len, hidden*2)
        lstm_out, _ = self.lstm(x)

        # Take the last time step
        last_hidden = lstm_out[:, -1, :]

        x = self.relu(self.fc1(last_hidden))
        x = self.dropout(x)
        x = self.fc2(x)
        return x
