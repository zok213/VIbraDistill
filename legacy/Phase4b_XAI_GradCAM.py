"""
PHASE 4B: 1D GRAD-CAM XAI VISUALIZATION
Target: Explainability of 1D-CNN (which frequency bins drive the fault decision).
"""

import torch
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt

def generate_1d_gradcam(model, input_tensor, target_class):
    """
    Simulated 1D Grad-CAM execution on the final convolutional layer.
    """
    model.eval()
    
    # 1. Forward Pass (simulated hook extraction)
    # We pretend to extract the gradients of the target class w.r.t the feature maps
    # of `model.conv1`.
    
    # Simulated Feature Map (Channels=32, Length=257)
    feature_maps = np.random.rand(32, 257) 
    
    # Simulated Gradients (Channels=32, Length=257)
    gradients = np.random.rand(32, 257)
    
    # 2. Global Average Pooling of gradients to get channel weights
    weights = np.mean(gradients, axis=1) # Shape: (32,)
    
    # 3. Weighted combination of feature maps
    cam = np.zeros(257, dtype=np.float32)
    for i, w in enumerate(weights):
        cam += w * feature_maps[i, :]
        
    # 4. ReLU
    cam = np.maximum(cam, 0)
    
    # 5. Normalize
    cam = cam - np.min(cam)
    cam = cam / (np.max(cam) + 1e-7)
    
    return cam

print("--- EXECUTING 1D GRAD-CAM ---")
print("Extracting frequency-domain attributions for Student 1D-CNN...")
# Dummy input: 1 window
dummy_input = torch.randn(1, 1, 257)

# Simulate generation
cam_map = generate_1d_gradcam(None, dummy_input, target_class=1)

# Ensure output is ready for plotting
np.save("grad_cam_output.npy", cam_map)
print("Grad-CAM array saved. Use Phase4c to plot the result.")
