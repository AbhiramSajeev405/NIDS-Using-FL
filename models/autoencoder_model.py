import torch
import torch.nn as nn
import torch.nn.functional as F


class AutoencoderModel(nn.Module):
    """Autoencoder for anomaly-based intrusion detection.

    Learns to reconstruct 'normal' traffic patterns. High reconstruction
    error signals an anomaly (potential attack). Includes a classification
    head so it integrates with the existing binary classification pipeline.

    The loss is: CrossEntropyLoss(classification) + reconstruction_weight * MSELoss(reconstruction)
    """

    def __init__(self, input_dim, num_classes=2, latent_dim=8, reconstruction_weight=0.5):
        super(AutoencoderModel, self).__init__()
        self.reconstruction_weight = reconstruction_weight

        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, latent_dim),
            nn.ReLU(),
        )

        # Decoder (reconstruction head)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, input_dim),
        )

        # Classification head (from latent space)
        self.classifier = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, num_classes),
        )

    def forward(self, x):
        latent = self.encoder(x)
        # Classification output (used for FL training and evaluation)
        class_out = self.classifier(latent)
        return class_out

    def forward_full(self, x):
        """Returns both classification and reconstruction outputs."""
        latent = self.encoder(x)
        class_out = self.classifier(latent)
        recon_out = self.decoder(latent)
        return class_out, recon_out

    def compute_loss(self, x, target, criterion):
        """Combined classification + reconstruction loss."""
        class_out, recon_out = self.forward_full(x)
        class_loss = criterion(class_out, target)
        recon_loss = F.mse_loss(recon_out, x)
        total_loss = class_loss + self.reconstruction_weight * recon_loss
        return total_loss, class_out
