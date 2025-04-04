from ultralytics import YOLO
import os
import torch

def load_model(model_path: str):
    """
    Carrega um modelo YOLO a partir do caminho fornecido.

    :param model_path: Caminho para o arquivo .pt do modelo YOLO.
    :return: Objeto do modelo carregado.
    :raises FileNotFoundError: Se o caminho do modelo não for encontrado.
    """
    
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Modelo não encontrado em: {model_path}")

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'[INFO] Usando dispositivo: {device}')
    print(torch.cuda.get_device_name(0))
    
    model = YOLO(model_path).to("cuda")
    print(f"[INFO] Modelo carregado com sucesso: {model_path}")

    return model, device

# model_path = "models/best.pt"
# model, device = load_model(model_path)