import os
import faiss
import logging
import numpy as np
from tqdm import tqdm

import torch
from torch.utils.data import DataLoader
from torch.utils.data.dataset import Subset

from utils import superglobal

def test(args, eval_ds, model):
    """Compute features of the given dataset and compute the recalls."""
    
    # if args.efficient_ram_testing:
        # return test_efficient_ram_usage(args, eval_ds, model, test_method)
    model = model.eval()
    with torch.no_grad():
        logging.debug("Extracting database features for evaluation/testing")
        # For database use "hard_resize", although it usually has no effect because database images have same resolution
        database_subset_ds = Subset(eval_ds, list(range(eval_ds.database_num)))
        database_dataloader = DataLoader(dataset=database_subset_ds, num_workers=args.num_workers,
                                         batch_size=args.infer_batch_size, pin_memory=True)
        all_features = np.empty((len(eval_ds), args.features_dim), dtype="float32")

        database_features_dir = os.path.join(args.datasets_folder, args.dataset_name, 'images/test', "database_features.npy")
        if os.path.isfile(database_features_dir) == 1:
            database_features = np.load(database_features_dir)
        else: 
            for inputs, indices in tqdm(database_dataloader, ncols=100):
                features = model(inputs.to("cuda"))
                features = features.cpu().numpy()
                # if pca is not None:
                #     features = pca.transform(features)
                all_features[indices.numpy(), :] = features

            database_features = all_features[:eval_ds.database_num]
            np.save(database_features_dir, database_features)
        
        logging.debug("Extracting queries features for evaluation/testing")
        queries_infer_batch_size = args.infer_batch_size
        queries_subset_ds = Subset(eval_ds, list(range(eval_ds.database_num, eval_ds.database_num+eval_ds.queries_num)))
        queries_dataloader = DataLoader(dataset=queries_subset_ds, num_workers=args.num_workers,
                                        batch_size=queries_infer_batch_size, pin_memory=True)
        for inputs, indices in tqdm(queries_dataloader, ncols=100):
            features = model(inputs.to("cuda"))
            features = features.cpu().numpy()
            # if pca is not None:
            #     features = pca.transform(features)
            
            all_features[indices.numpy(), :] = features
    
    queries_features = all_features[eval_ds.database_num:]
    # database_features = all_features[:eval_ds.database_num]

    MDescAug_obj = superglobal.MDescAug()
    RerankwMDA_obj = superglobal.RerankwMDA()
    queries_features = torch.tensor(queries_features).cuda()
    database_features = torch.tensor(database_features).cuda()

    sim = torch.matmul(database_features, queries_features.T)
    ranks = torch.argsort(-sim, axis=0)

    rerank_dba_final, res_top1000_dba, ranks_trans_1000_pre, x_dba = MDescAug_obj(database_features, queries_features, ranks)
    ranks = RerankwMDA_obj(ranks, rerank_dba_final, res_top1000_dba, ranks_trans_1000_pre, x_dba)
    ranks = ranks.data.cpu().numpy()

    print(ranks.shape)

    
    faiss_index = faiss.IndexFlatL2(args.features_dim)
    faiss_index.add(database_features)
    del database_features, all_features
    
    logging.debug("Calculating recalls")
    distances, predictions = faiss_index.search(queries_features, max(args.recall_values))

    #### For each query, check if the predictions are correct
    positives_per_query = eval_ds.get_positives()
    # args.recall_values by default is [1, 5, 10, 20]
    recalls = np.zeros(len(args.recall_values))
    for query_index, pred in enumerate(predictions):
        for i, n in enumerate(args.recall_values):
            if np.any(np.in1d(pred[:n], positives_per_query[query_index])):
                recalls[i:] += 1
                break
    # Divide by the number of queries*100, so the recalls are in percentages
    recalls = recalls / eval_ds.queries_num * 100
    recalls_str = ", ".join([f"R@{val}: {rec:.1f}" for val, rec in zip(args.recall_values, recalls)])
    return recalls, recalls_str