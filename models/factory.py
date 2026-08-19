"""Model Factory — Plug-and-Play model instantiation from config strings."""


def get_model(model_name, input_dim, num_classes=2):
    """Dynamically loads and instantiates the requested model.

    Args:
        model_name: One of 'mlp', 'cnn', 'lstm', 'resnet', 'autoencoder'
        input_dim: Number of input features (unified feature space size)
        num_classes: Number of output classes (default: 2 for binary)

    Returns:
        A PyTorch nn.Module instance
    """
    name = model_name.lower()

    # Lazy-load models to avoid circular imports
    if name == 'cnn':
        from .cnn_model import CNNModel
        return CNNModel(input_dim, num_classes)
    elif name == 'mlp':
        from .mlp_model import MLPModel
        return MLPModel(input_dim, num_classes)
    elif name == 'lstm':
        from .lstm_model import LSTMModel
        return LSTMModel(input_dim, num_classes)
    elif name == 'resnet':
        from .resnet_model import ResNetModel
        return ResNetModel(input_dim, num_classes)
    elif name == 'autoencoder':
        from .autoencoder_model import AutoencoderModel
        return AutoencoderModel(input_dim, num_classes)
    else:
        available = ['mlp', 'cnn', 'lstm', 'resnet', 'autoencoder']
        raise ValueError(f"Model type '{model_name}' not recognized. Options: {available}")


def list_models():
    """Returns list of all available model names."""
    return ['mlp', 'cnn', 'lstm', 'resnet', 'autoencoder']
