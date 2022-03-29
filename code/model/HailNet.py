import torch
from torch import nn
import matplotlib.pyplot as plt
import torch.nn.functional as F


class GNNLayer(nn.Module):
    def __init__(self, n, long, lat):
        super().__init__()
        self.lin1 = nn.Linear(long * lat, 16*16)
        indecies = [[], []]
        values = []
        for j in range(long * lat):
            indecies[0].append(j)
            indecies[1].append(j)
            values.append(1)
        for i in range(lat + 1, (long - 1) * lat - 1):
            x = i
            for y in (i - 1, i + 1, i + lat, i - lat, i + lat - 1, i + lat + 1, i - lat - 1, i - lat + 1):
                indecies[0].append(x)
                indecies[1].append(y)
            for y in (i - 1, i + 1, i + lat, i - lat, i + lat - 1, i + lat + 1, i - lat - 1, i - lat + 1):
                indecies[0].append(y)
                indecies[1].append(x)
            for i in range(16):
                values.append(1)

        indecies = torch.Tensor(indecies)
        values = torch.Tensor(values)
        self.A1 = torch.sparse_coo_tensor(indecies, values, (long * lat, long * lat))
        self.A1 = self.A1.float()

    def forward(self, x):
        x_flatten = x.flatten(start_dim=1)
        h1 = self.A1 @ x_flatten.T.float()
        h1 = h1.T
        h2 = self.lin1(h1)
        return h2


class HailNet(nn.Module):
    def __init__(self, n, long, lat, gru_hidden_size, gru_num_layers, lin1_size=16, seq_len=12, units=None):
        super().__init__()
        self.n = n
        self.long = long
        self.lat = lat
        self.gru_hidden_size = gru_hidden_size
        self.lin1_size = lin1_size
        self.gru_num_layers = gru_num_layers
        self.seq_len = seq_len
        self.units = units
        self.embedding_layer = GNNLayer(n, long, lat)
        self.lin1 = nn.Linear(self.lin1_size * self.lin1_size, 1)
        self.gru = nn.GRU(
            input_size=self.lin1_size * self.lin1_size,
            hidden_size=self.gru_hidden_size,
            num_layers=self.gru_num_layers,
            batch_first=True
        )
        if units is None:
            self.fully_connected_layer = self.fully_connected()
        else:
            self.fully_connected_layer = self.fully_connected(self.units)

    @staticmethod
    def fully_connected(units: list = [16*16, 16, 16]):
        net = nn.Sequential()
        for i, unit in enumerate(units):
            if i == len(units) - 1:
                net.add_module(f'linear {i}', torch.nn.Linear(unit, 1))
                net.add_module(f'sigmoid {i}', torch.sigmoid())
            else:
                net.add_module(f'linear {i}', torch.nn.Linear(unit, unit[i+1]))
                net.add_module(f'sigmoid {i}', torch.sigmoid())
        return net

    def forward(self, x):
        # x -> (n, seq_len, long, lat)
        h0 = torch.randn(self.gru_num_layers, x.size(0), self.gru_hidden_size)  # hidden cell for gru
        hs1 = []
        for i in range(self.seq_len):
            t1 = self.embedding_layer(x[:][i])
            t2 = torch.sigmoid(t1)
            t3 = self.lin1(t2)
            t4 = torch.sigmoid(t3)
            hs1.append(t4)
        t = torch.Tensor(x.shape[0], x.shape[1], self.lin1_size * self.lin1_size)
        torch.cat(hs1, out=t)
        # t -> (bacth_size, seq_len, lin1*lin1)
        out, _ = self.gru(t, h0)
        out = out[:, -1, :]
        out = self.fully_connected_layer(out)

        return out


def train(num_epochs: int, model, loss_fn, opt, train_dl: torch.utils.data.DataLoader):
    losses = []
    for epoch in range(num_epochs):
        model.train()
        for i, (xb, yb) in enumerate(train_dl):
            pred = model(xb)
            opt.zero_grad()
            loss = loss_fn(pred, yb)

            loss.backward()
            opt.step()

        losses.append(loss.detach().item())
        print(f'Epoch: {epoch} | Loss: {loss.detach().item()}')
    return losses


def test(model, test_dl: torch.utils.data.DataLoader, metrics: list, metrics_funcs: dict):
    with torch.no_grad():
        model.eval()
        predictions = []
        true_values = []
        metrics_values = {}.fromkeys(metrics)
        for xt, yt in test_dl:
            predictions.append(model(xt))
            true_values.append(yt)
            plt.figure(figsize=(10, 5))
            plt.imshow(xt.numpy()[0], cmap='hot', interpolation='nearest')
            plt.show()
            print(f"target: {yt.item()}, prediction: {model(xt).item()}")
        #for metric in metrics:
        #    metrics_values[metric] = metrics_funcs[metric](predictions, true_values)
    return predictions, true_values#, metrics_values
