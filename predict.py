import torch
import argparse
import sys

from scripts.model import Decoder
from scripts.process_input import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('complex_pdb', type=str)
    parser.add_argument('chains_info', type=str, help="e.g. HL:B")
    parser.add_argument('mutation_info', type=str, help="e.g. B:S40T")
    parser.add_argument('--load_model', default='./ckpt/pre-trained_model.pt')

    args = parser.parse_args()
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load pre-trained model config
    ckpt = torch.load(args.load_model, map_location=device)
    config = ckpt['config']
    config_namespace = argparse.Namespace(**config)
    weight = ckpt['model_state']
    
    # Initialize the model and load weights with strict=False
    model = Decoder(config_namespace).to(device)
    model.load_state_dict(weight, strict=False)
    vars(args).update(vars(config_namespace))

    # No ESM model is loaded since the pretrained model uses W_s (trainable 21-dim embedding).

    with torch.no_grad():
        model.eval()
        
        # Parse PDB
        print(f"Parsing PDB {args.complex_pdb} with chains {args.chains_info}...")
        try:
            protein = Proteins(args.complex_pdb, args.chains_info)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error parsing PDB: {e}")
            sys.exit(1)
            
        print(f"Applying mutation {args.mutation_info}...")
        try:
            mut_proteins = get_chains_dict(args.mutation_info, protein.complex)
        except MutationMismatchError as e:
            print(f"Mutation Mismatch Error: {e}")
            sys.exit(1)
            
        # Generate feature tensors (no ESM used for the pretrained model)
        complex_features = completize(mut_proteins, esm=None)
        
        # The pretrained model expects 6 features (without B_factor).
        complex_features[-1] = None
        
        complex_features = [c.to(device) if isinstance(c, torch.Tensor) else c for c in complex_features]
        
        print("Running inference...")
        ddG_pre = model(*complex_features)
        print(f'Predicted ddG value for input mutant is: {ddG_pre.item():.3f} kcal/mol.')
