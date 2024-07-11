from torch import nn

from models import dinov2_network
import models.aggregations as aggregations

import torchvision.transforms as transforms


class VGLNet(nn.Module):

    def __init__(self, args):
        super().__init__()
        self.backbone = dinov2_network.DINOv2(backbone=args.backbone,
                               trainable_layers=args.trainable_layers)
        
        self.aggregation = get_aggregation(args)
        
    def forward(self, x):

        x = self.backbone(x)
        x = self.aggregation(x)
        return x
    
class VGLNet_Test(nn.Module):

    def __init__(self, args):
        super().__init__()
        self.backbone = dinov2_network.DINOv2(backbone=args.backbone,
                               trainable_layers=args.trainable_layers)
        
        self.aggregation = get_aggregation(args)
        
    def forward(self, x):

        if not self.training:
            b, c, h, w = x.shape
            h = round(h / 14) * 14
            w = round(w / 14) * 14
            x = transforms.functional.resize(x, [h, w], antialias=True)

        x = self.backbone(x)
        x = self.aggregation(x)
        return x
    

def get_aggregation(args):
    if args.aggregation == "salad":
        return aggregations.SALAD(num_channels = dinov2_network.CHANNELS_NUM[args.backbone])
    elif args.aggregation == "netvlad":
        return aggregations.NetVLAD(clusters_num=args.clusters, dim=dinov2_network.CHANNELS_NUM[args.backbone], work_with_tokens=args.use_cls, linear_dim= args.linear_dim, work_with_linear = args.use_linear)
    elif args.aggregation == "cosgem":
        return aggregations.CosGeM(features_dim=dinov2_network.CHANNELS_NUM[args.backbone], fc_output_dim=args.features_dim)
    elif args.aggregation == "cls":
        return aggregations.CLS()
    elif args.aggregation == "g2m":
        return aggregations.G2M(
            num_channels=dinov2_network.CHANNELS_NUM[args.backbone],
            fc_output_dim=dinov2_network.CHANNELS_NUM[args.backbone],
            num_hiddens=args.num_hiddens,
            use_cls=args.use_cls,
            use_ca=args.use_ca,
            pooling_method=args.ca_method,
        )
