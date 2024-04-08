import os
import logging
from datetime import datetime
import torch

from utils import parser, commons, util, test
from models import vgl_network
from datasets import base_dataset

args = parser.parse_arguments()
start_time = datetime.now()
args.save_dir = os.path.join("logs", args.save_dir, args.backbone, args.dataset_name)
commons.setup_logging(args.save_dir)
commons.make_deterministic(args.seed)
logging.info(f"Arguments: {args}")
logging.info(f"The outputs are being saved in {args.save_dir}")

model = vgl_network.VGLNet(args)
model = model.to("cuda")
logging.info(f"Resuming model from {args.resume}")
model = util.resume_model(args, model)
model = torch.nn.DataParallel(model)

test_ds = base_dataset.BaseDataset(args, "test")
logging.info(f"Test set: {test_ds}")

######################################### TEST on TEST SET #########################################
recalls, recalls_str = test.test(args, test_ds, model)
logging.info(f"Recalls on {test_ds}: {recalls_str}")

logging.info(f"Finished in {str(datetime.now() - start_time)[:-7]}")