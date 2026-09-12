# abCAN-DRUGS: Antibody Mutation Affinity Analysis

![abCAN Architecture](https://github.com/ChenGong57/abCAN/blob/main/data/architecture.png)

**abCAN-DRUGS** is a modernized computational biology platform built on the original **abCAN** (Attention Network for Predicting Mutant Antibody Affinity) architecture. 

It provides an end-to-end pipeline for predicting mutation-induced binding affinity changes ($\Delta\Delta G$) in antibody-antigen complexes using Geometric Deep Learning. The platform features an automated optimization API and a stunning, interactive 3D web dashboard designed for structural biologists and protein engineers.

---

## 🔬 How It Works (Demo Workflow)

The abCAN-DRUGS platform streamlines the process of discovering affinity-enhancing mutations:

1. **Load Structure**: Upload an `antibody-antigen.pdb` file directly into the dashboard.
2. **Detect Interface**: The system automatically calculates atomic distances and identifies antibody residues within 5.0 Å of the antigen.
3. **Select / Screen Mutations**: Choose a specific targeted mutation, or run a **Global Interface Screen** to exhaustively evaluate substitutions across the entire binding footprint.
4. **Pretrained abCAN**: The core Geometric Deep Learning model processes the structural context (spatial graphs, node features) and predicts the $\Delta\Delta G$.
5. **Results**: Review the sorted list of potential mutation candidates (ranked from most to least stabilizing).
6. **3D Visualization**: Click any candidate to instantly jump to that position in the interactive 3D viewer and read the scientific prediction explanation.

---

## 🛠 Architecture Overview

The project is divided into two primary components:

### 1. Geometric Deep Learning Model
- Takes a pre-mutant (wild-type) PDB structure and a target mutation as input.
- Constructs spatial graphs representing the atomic neighborhoods.
- Utilizes attention-based graph neural networks to predict the change in affinity ($\Delta\Delta G$) upon mutation.

### 2. Full-Stack Platform
- **Backend (FastAPI)**: Exposes RESTful endpoints for targeted optimization, combinatorial mutation evaluation, and global interface screening. Manages a robust caching layer for PDB parsing to ensure rapid inference.
- **Frontend (React + Vite + 3Dmol.js)**: A sleek, dark-mode, glassmorphism UI tailored for computational biology. Provides interactive data tables tightly coupled with a hardware-accelerated 3D molecular viewer.

---

## 💻 Installation

### Prerequisites
- Python 3.8+
- Node.js (for the frontend dashboard)
- CUDA >= 11.8 (if running with GPU acceleration)

### Backend Setup (Python)
1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/ChenGong57/abCAN.git
   cd abCAN
   ```
2. Install the required Python packages:
   ```bash
   pip install torch==2.0.0 numpy==1.24.3 fastapi uvicorn pydantic biopython
   ```
3. Start the FastAPI server:
   ```bash
   python server.py
   ```
   *The backend will run on `http://localhost:8000`.*

### Frontend Setup (Node.js)
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the required NPM packages:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *The frontend will run on `http://localhost:5173`.*

---

## 🌐 API Reference

The FastAPI backend exposes the following endpoints:

- `POST /optimize/single`: Evaluates all 19 standard amino acid substitutions for a single target position.
- `POST /optimize/multi`: Evaluates combinatorial mutations across multiple specified positions.
- `POST /optimize/screen`: Automatically identifies the antibody-antigen interface and exhaustively screens all possible substitutions across the entire interface.

All endpoints accept JSON payloads specifying the `filename` (PDB file located in `data/pdbs/`) and the `chains` string (e.g., `"A_B"` or `"HL_A"`).

---

## ⚡ Inference (CLI Usage)

If you prefer to run predictions via the command line without the UI, you can use the original `predict.py` script.

### Input Format
The model requires a wild-type complex PDB and a specific chain format string: `[Antibody Chains]_[Antigen Chains]`. 
For example, if chains H and L are the antibody and chain A is the antigen, use `HL_A`.

### Mutation Format
Specify mutations using the format `[Original Residue][Chain][Position][New Residue]`. Multiple mutations should be comma-separated.

### Example
To predict the $\Delta\Delta G$ for five simultaneous mutations on the `2B2X.pdb` complex:
```bash
python predict.py ./data/2B2X.pdb HL_A VH50T,EH64K,FH99W,QL28S,YL52N
```

---

## ⚠️ Limitations & Future Work

- **Multi-Mutation Dependencies**: The current architecture evaluates mutations somewhat independently. Complex combinatorial effects (epistasis) may require advanced joint-distribution modeling in future iterations.
- **Uncertainty Estimation**: $\Delta\Delta G$ predictions currently lack calibrated confidence metrics. Future implementations will explore MC dropout and ensemble inference to provide robust uncertainty bounds.
- **Computational Overhead**: Global interface screening performs hundreds of sequential forward passes. While optimized via caching, screening very large interfaces on CPU may take 1-2 minutes. GPU execution is highly recommended for bulk evaluations.
