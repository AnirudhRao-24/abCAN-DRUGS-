from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import torch
import shutil
import os
import argparse
from scripts.model import Decoder
from scripts.process_input import Proteins
from optimize import optimize_position, predict_mutation, identify_interface_residues
import itertools

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Global model and protein cache
MODEL = None
PROTEIN_CACHE = {}
PROTEINS_OBJ_CACHE = {}

def load_model():
    global MODEL
    if MODEL is None:
        ckpt = torch.load('./ckpt/pre-trained_model.pt', map_location=device)
        config = argparse.Namespace(**ckpt['config'])
        MODEL = Decoder(config).to(device)
        MODEL.load_state_dict(ckpt['model_state'], strict=False)
        MODEL.eval()

@app.on_event("startup")
def startup_event():
    load_model()
    os.makedirs("uploads", exist_ok=True)
    # Cache the default 1a22.pdb
    if os.path.exists("data/pdbs/1a22.pdb"):
        shutil.copy("data/pdbs/1a22.pdb", "uploads/1a22.pdb")
        try:
            protein = Proteins("uploads/1a22.pdb", "A_B")
            PROTEIN_CACHE["1a22.pdb"] = protein.complex
            PROTEINS_OBJ_CACHE["1a22.pdb"] = protein
        except Exception as e:
            pass

@app.post("/upload")
async def upload_pdb(file: UploadFile = File(...), chains: str = Form("A_B")):
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Pre-parse protein
    try:
        protein = Proteins(file_path, chains)
        PROTEIN_CACHE[file.filename] = protein.complex
        PROTEINS_OBJ_CACHE[file.filename] = protein
    except Exception as e:
        return {"error": str(e)}
        
    return {"filename": file.filename, "message": "Uploaded and parsed successfully"}

@app.get("/pdb/{filename}")
async def get_pdb(filename: str):
    return FileResponse(f"uploads/{filename}")

class SingleOptRequest(BaseModel):
    filename: str
    position: str

@app.post("/optimize/single")
async def optimize_single(req: SingleOptRequest):
    if req.filename not in PROTEIN_CACHE:
        return {"error": "PDB not found in cache"}
    
    try:
        res = optimize_position(MODEL, PROTEIN_CACHE[req.filename], None, device, req.position)
        return {"results": res}
    except Exception as e:
        return {"error": str(e)}

class MultiOptRequest(BaseModel):
    filename: str
    positions: List[str]
    top_k: int = 3

@app.post("/optimize/multi")
async def optimize_multi(req: MultiOptRequest):
    if req.filename not in PROTEIN_CACHE:
        return {"error": "PDB not found in cache"}
        
    try:
        candidate_lists = []
        for pos_str in req.positions:
            res = optimize_position(MODEL, PROTEIN_CACHE[req.filename], None, device, pos_str, top_k=req.top_k)
            candidate_lists.append([r['mutation'] for r in res])
            
        combo_results = []
        for combo in itertools.product(*candidate_lists):
            multi_mut_str = ",".join(combo)
            ddg = predict_mutation(MODEL, PROTEIN_CACHE[req.filename], None, device, multi_mut_str)
            if ddg is not None:
                combo_results.append({'mutation': multi_mut_str, 'ddg': ddg})
                
        combo_results = sorted(combo_results, key=lambda x: x['ddg'])
        return {"results": combo_results}
    except Exception as e:
        return {"error": str(e)}

class ScreenRequest(BaseModel):
    filename: str
    chains: str

@app.post("/optimize/screen")
async def optimize_screen(req: ScreenRequest):
    if req.filename not in PROTEINS_OBJ_CACHE:
        return {"error": "PDB not found in cache"}
        
    try:
        protein_obj = PROTEINS_OBJ_CACHE[req.filename]
        # 1. Identify interface residues
        interface_residues = identify_interface_residues(protein_obj, req.chains, distance_threshold=5.0)
        
        if not interface_residues:
            return {"error": "No interface residues found."}
            
        # 2. Optimize each position
        all_results = []
        for pos_str in interface_residues:
            res = optimize_position(MODEL, protein_obj.complex, None, device, pos_str, top_k=None)
            for r in res:
                r['position'] = pos_str
                all_results.append(r)
                
        # 3. Sort globally
        all_results = sorted(all_results, key=lambda x: x['ddg'])
        
        # Limit to top 100 to prevent huge payloads
        return {"results": all_results[:100]}
    except Exception as e:
        return {"error": str(e)}

class ExplainRequest(BaseModel):
    filename: str
    mutation: str # e.g. FA25L
    chains: str

@app.post("/explain")
async def explain_prediction(req: ExplainRequest):
    if req.filename not in PROTEINS_OBJ_CACHE:
        return {"error": "PDB not found in cache"}
        
    protein_obj = PROTEINS_OBJ_CACHE[req.filename]
    
    # We might have combinatorial mutations e.g. FA25L,DA26C
    # Let's explain just the first one, or return a list
    muts = req.mutation.split(',')
    contexts = []
    
    for mut in muts:
        mut = mut.strip()
        ori_aa = mut[0]
        chain_id = mut[1]
        new_aa = mut[-1]
        try:
            pos = int(mut[2:-1])
        except:
            pos = int(mut[2:-2])
            
        ctx = protein_obj.get_structural_context(chain_id, pos, req.chains)
        if ctx:
            contexts.append({
                'mutation': mut,
                'position': pos,
                'original_residue': ori_aa,
                'new_residue': new_aa,
                'distance_to_antigen': ctx['distance_to_antigen'],
                'is_interface': ctx['is_interface'],
                'neighborhood': ctx['neighborhood']
            })
            
    return {"contexts": contexts}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
