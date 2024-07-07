import os
import logging
from datetime import datetime
import torch

from utils import parser, commons, util, test, test_vis, test_embodied
from models import vgl_network, dinov2_network
from datasets import base_dataset

from peft import PeftModel

args = parser.parse_arguments()
start_time = datetime.now()
args.save_dir = os.path.join("logs", args.save_dir, args.backbone + "_" + args.aggregation, args.dataset_name, start_time.strftime('%Y-%m-%d_%H-%M-%S'))
commons.setup_logging(args.save_dir)
commons.make_deterministic(args.seed)
logging.info(f"Arguments: {args}")
logging.info(f"The outputs are being saved in {args.save_dir}")

model = vgl_network.VGLNet_Test(args)
# model = dinov2_network.DINOv2(backbone=args.backbone) # used for PCA Vis
model = model.to("cuda")
if args.aggregation == "netvlad":
    args.features_dim = args.clusters * dinov2_network.CHANNELS_NUM[args.backbone]
    if args.use_cls:
        args.features_dim = args.clusters * args.linear_dim + 256
        
if args.resume != None:
    if args.use_lora:
        logging.info(f"Resuming lora model from {args.resume}")
        model = PeftModel.from_pretrained(model, args.resume)
    else:
        logging.info(f"Resuming model from {args.resume}")
        model = util.resume_model(args, model)
    
model = torch.nn.DataParallel(model)

if args.pca_dim is None:
    pca = None
else:
    full_features_dim = args.features_dim
    args.features_dim = args.pca_dim
    pca = util.compute_pca(args, model, args.pca_dataset_folder, full_features_dim)

test_ds = base_dataset.BaseDataset(args, "test")
logging.info(f"Test set: {test_ds}")

######################################### TEST on TEST SET #########################################
recalls, recalls_str = test.test(args, test_ds, model)

######################################### Vis on DEMO SET ########################################

# test_vis.test(args, test_ds, model)

######################################### EMBODIED TEST on TEST SET #########################################
# recalls, recalls_str = test_embodied.test(args, test_ds, model)

logging.info(f"Recalls on {test_ds}: {recalls_str}")

logging.info(f"Finished in {str(datetime.now() - start_time)[:-7]}")

