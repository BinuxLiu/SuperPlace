import torch
import numpy as np

class BoQBlock(torch.nn.Module):
    def __init__(self, in_dim, num_queries, nheads=8):
        super(BoQBlock, self).__init__()

        self.encoder = torch.nn.TransformerEncoderLayer(d_model=in_dim, nhead=nheads, dim_feedforward=4*in_dim, batch_first=True, dropout=0.)
        self.queries = torch.nn.Parameter(torch.randn(1, num_queries, in_dim))
        
        # the following two lines are used during training only, you can cache their output in eval.
        self.self_attn = torch.nn.MultiheadAttention(in_dim, num_heads=nheads, batch_first=True)
        self.norm_q = torch.nn.LayerNorm(in_dim)
        #####
        
        self.cross_attn = torch.nn.MultiheadAttention(in_dim, num_heads=nheads, batch_first=True)
        self.norm_out = torch.nn.LayerNorm(in_dim)
        

    def forward(self, x):
        B = x.size(0)
        x = self.encoder(x)
        
        q = self.queries.repeat(B, 1, 1)
        
        # the following two lines are used during training.
        # for stability purposes 
        q = q + self.self_attn(q, q, q)[0]
        q = self.norm_q(q)
        #######
        
        out, attn = self.cross_attn(q, x, x)        
        out = self.norm_out(out)
        return x, out, attn.detach()


class BoQ(torch.nn.Module):
    def __init__(self, in_channels=1024, proj_channels=512, num_queries=32, num_layers=2, row_dim=32, work_with_linear = True):
        super().__init__()
        
        self.work_with_linear = work_with_linear
        self.proj_c = torch.nn.Conv2d(in_channels, proj_channels, kernel_size=3, padding=1)
        self.norm_input = torch.nn.LayerNorm(proj_channels)
        
        in_dim = proj_channels
        self.boqs = torch.nn.ModuleList([
            BoQBlock(in_dim, num_queries, nheads=in_dim//64) for _ in range(num_layers)])
        
        self.fc = torch.nn.Linear(num_layers*num_queries, row_dim)
        
    def forward(self, x):
        # reduce input dimension using 3x3 conv when using ResNet
        x, _ = x
        x = self.proj_c(x)
        x = x.flatten(2).permute(0, 2, 1)
        x = self.norm_input(x)
        
        outs = []
        attns = []
        for i in range(len(self.boqs)):
            x, out, attn = self.boqs[i](x)
            outs.append(out)
            attns.append(attn)

        out = torch.cat(outs, dim=1)
        if self.work_with_linear:
            out = self.fc(out.permute(0, 2, 1))
            out = out.flatten(1)
            out = torch.nn.functional.normalize(out, p=2, dim=-1)
        else:
            out = torch.nn.functional.normalize(out, p=2, dim=2)
            out = out.flatten(1)
            out = torch.nn.functional.normalize(out, p=2, dim=-1)
        # return out, attns
        return out
    
def print_nb_params(m):
    model_parameters = filter(lambda p: p.requires_grad, m.parameters())
    params = sum([np.prod(p.size()) for p in model_parameters])
    print(f"Trainable parameters: {params/1e6:.3}M")
    
    
def main():
    import torch.cuda.amp as amp  
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(device)
    x = (torch.randn(1, 768, 16, 16, device=device), torch.randn(1, 768, device=device))  

    agg = BoQ(
            in_channels=768,  # make sure the backbone has out_channels attribute
            proj_channels=384,
            num_queries=64,
            num_layers=2,
            row_dim=32, # 32 for dinov2
            # work_with_linear = False,
        ).to(device)
    
    scaler = amp.GradScaler()  
    import time
    print_nb_params(agg)
    start_time = time.time()
    for _ in range(3000): 
        with torch.cuda.amp.autocast():  
            output = agg(x)  
    end_time = time.time()
   
    average_time = (end_time - start_time) / 3000  
    print(f'Average time per pass: {average_time:.6f} seconds')
    print(output.shape)


if __name__ == "__main__":
    main()