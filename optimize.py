import torch
import argparse
import sys
import copy
import itertools

from scripts.model import Decoder
from scripts.process_input import Proteins, get_chains_dict, completize, MutationMismatchError, alphabet

def predict_mutation(model, protein_complex, esm_model_info, device, mutation_str):
    strct = copy.deepcopy(protein_complex)
    try:
        mut_proteins = get_chains_dict(mutation_str, strct)
    except MutationMismatchError as e:
        print(f"Mutation Mismatch Error: {e}")
        return None
    except Exception as e:
        print(f"Error applying mutation: {e}")
        return None

    complex_features = completize(mut_proteins, esm=None)
    complex_features[-1] = None  # Remove B_factor
    complex_features = [c.to(device) if isinstance(c, torch.Tensor) else c for c in complex_features]

    with torch.no_grad():
        ddG_pre = model(*complex_features)
    
    return ddG_pre.item()

def get_wildtype(protein_complex, position_str):
    # position_str is like A:25
    chain_name, pos = position_str.split(':')
    pos = int(pos)
    if chain_name not in protein_complex:
        raise ValueError(f"Chain {chain_name} not found in PDB.")
    
    seq_index = protein_complex[chain_name]['seq_index']
    if pos not in seq_index:
        raise ValueError(f"Position {pos} not found in chain {chain_name}.")
    
    idx = seq_index.index(pos)
    wt_aa = protein_complex[chain_name]['sequence'][idx]
    return wt_aa, chain_name, pos

def optimize_position(model, protein_complex, esm_model_info, device, pos_str, top_k=None):
    wt_aa, chain_name, pos = get_wildtype(protein_complex, pos_str)
    print(f"Optimizing position {pos_str} (Wildtype: {wt_aa})")
    
    standard_aas = [a for a in alphabet if a not in ['-', wt_aa]]
    results = []
    
    for mut_aa in standard_aas:
        mut_str = f"{wt_aa}{chain_name}{pos}{mut_aa}"
        ddg = predict_mutation(model, protein_complex, esm_model_info, device, mut_str)
        if ddg is not None:
            results.append({'mutation': mut_str, 'ddg': ddg})
            
    # Sort by ddG (most negative / stabilizing first)
    results = sorted(results, key=lambda x: x['ddg'])
    
    if top_k is not None:
        results = results[:top_k]
        
    return results

def identify_interface_residues(protein_complex_obj, chains_info, distance_threshold=5.0):
    """
    Identifies all antibody residues that are within `distance_threshold` of the antigen.
    protein_complex_obj is an instance of Proteins (from process_input).
    chains_info is a string like "A_B" where left of '_' is antibody, right is antigen.
    """
    ab_chains = chains_info.split('_')[0]
    interface_residues = []
    
    for chain_id in ab_chains:
        if chain_id not in protein_complex_obj.complex:
            continue
        
        seq_index = protein_complex_obj.complex[chain_id]['seq_index']
        for pos in seq_index:
            ctx = protein_complex_obj.get_structural_context(chain_id, pos, chains_info)
            if ctx and ctx.get('distance_to_antigen') is not None and ctx['distance_to_antigen'] <= distance_threshold:
                interface_residues.append(f"{chain_id}:{pos}")
                
    return interface_residues

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mutation Optimization Workflow")
    parser.add_argument('complex_pdb', type=str, help="Path to complex PDB")
    parser.add_argument('chains_info', type=str, help="e.g. A_B")
    parser.add_argument('--single', type=str, nargs='+', help="Single positions to optimize, e.g. A:25 B:10")
    parser.add_argument('--multi', type=str, nargs='+', help="Multi positions for combinatorial optimization, e.g. A:25 B:10")
    parser.add_argument('--top_k', type=int, default=3, help="Top K candidates to keep for combinatorial optimization")
    parser.add_argument('--load_model', default='./ckpt/pre-trained_model.pt')

    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load pre-trained model config
    ckpt = torch.load(args.load_model, map_location=device)
    config = ckpt['config']
    config_namespace = argparse.Namespace(**config)
    weight = ckpt['model_state']
    
    model = Decoder(config_namespace).to(device)
    model.load_state_dict(weight, strict=False)
    model.eval()

    print(f"Parsing PDB {args.complex_pdb} with chains {args.chains_info}...")
    try:
        protein = Proteins(args.complex_pdb, args.chains_info)
    except Exception as e:
        print(f"Error parsing PDB: {e}")
        sys.exit(1)
        
    if args.single:
        print("\n--- SINGLE MUTATION OPTIMIZATION ---")
        for pos_str in args.single:
            res = optimize_position(model, protein.complex, None, device, pos_str)
            print(f"\nTop Candidates for {pos_str}:")
            for i, r in enumerate(res[:5]): # Show top 5
                print(f"  {i+1}. {r['mutation']}: {r['ddg']:.3f} kcal/mol")
                
    if args.multi:
        print("\n--- MULTI-POSITION COMBINATORIAL OPTIMIZATION ---")
        candidate_lists = []
        for pos_str in args.multi:
            res = optimize_position(model, protein.complex, None, device, pos_str, top_k=args.top_k)
            candidate_lists.append([r['mutation'] for r in res])
            
        print(f"\nEvaluating {len(list(itertools.product(*candidate_lists)))} combinations...")
        
        combo_results = []
        for combo in itertools.product(*candidate_lists):
            multi_mut_str = ",".join(combo)
            ddg = predict_mutation(model, protein.complex, None, device, multi_mut_str)
            if ddg is not None:
                combo_results.append({'mutation': multi_mut_str, 'ddg': ddg})
                
        combo_results = sorted(combo_results, key=lambda x: x['ddg'])
        print("\nTop Combinatorial Candidates:")
        for i, r in enumerate(combo_results[:10]):
            print(f"  {i+1}. {r['mutation']}: {r['ddg']:.3f} kcal/mol")
