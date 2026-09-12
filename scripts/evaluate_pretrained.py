import os
import sys
import torch
import numpy as np
import pandas as pd
from tqdm import tqdm
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from torch.utils.data import DataLoader

# Ensure the parent directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from training.dataset import abCANDataset, collate_fn
from scripts.model import Decoder

class Config:
    esm = True
    batch_tokens = 70
    L_max = 1500
    depth = 4
    vocab_size = 21
    block_size = 32
    num_rbf = 8
    pos_dims = 16
    k_neighbors = 9
    hidden_size = 128
    dropout = 0.1
    seq_neighbors = 30

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load dataset
    print("Loading test dataset (M515)...")
    test_raw = abCANDataset('data/splits/test.csv', 'data/pdbs', log_file='logs/null.jsonl')
    
    # We load it directly into memory
    class InMemoryDataset(torch.utils.data.Dataset):
        def __init__(self, original_dataset):
            self.items = []
            print(f"Caching dataset of size {len(original_dataset)} in memory...")
            for i in tqdm(range(len(original_dataset))):
                item = original_dataset[i]
                if item is not None:
                    self.items.append(item)
        def __len__(self):
            return len(self.items)
        def __getitem__(self, idx):
            return self.items[idx]

    test_dataset = InMemoryDataset(test_raw)
    test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False, collate_fn=collate_fn)

    # Initialize model
    print("Initializing model...")
    model = Decoder(Config)
    
    # Load pretrained weights
    ckpt_path = 'ckpt/pre-trained_model.pt'
    print(f"Loading weights from {ckpt_path}...")
    ckpt = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt['model_state'], strict=False)
    model.to(device)
    model.eval()

    y_true = []
    y_pred = []

    print("Evaluating...")
    with torch.no_grad():
        for batch in tqdm(test_loader):
            if batch is None:
                continue
            
            # Unpack batch
            batch_complex, batch_ddg = batch
            complex_tensors = [t.unsqueeze(0).to(device) if t is not None else None for t in batch_complex[0]]
            
            # The pretrained model expects 6 features (without B_factor). 
            # The B_factor is the last element in complex_tensors before passing to model.
            complex_tensors[-1] = None 
            
            ddG = batch_ddg[0].to(device)
            
            # Predict
            pred = model(*complex_tensors)
            
            y_pred.append(pred.item())
            y_true.append(ddG.item())
            
    # Calculate metrics
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    pcc, _ = pearsonr(y_true, y_pred)
    spearman, _ = spearmanr(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    
    print("\n--- Final M515 Evaluation Metrics ---")
    print(f"PCC:      {pcc:.4f}")
    print(f"RMSE:     {rmse:.4f}")
    print(f"Spearman: {spearman:.4f}")
    print(f"MAE:      {mae:.4f}")
    print(f"R2:       {r2:.4f}")
    print("-------------------------------------")
    
    # Save predictions
    results_df = pd.DataFrame({'True_ddG': y_true, 'Pred_ddG': y_pred})
    os.makedirs('results', exist_ok=True)
    results_df.to_csv('results/m515_predictions.csv', index=False)
    print("Saved predictions to results/m515_predictions.csv")

if __name__ == '__main__':
    main()
