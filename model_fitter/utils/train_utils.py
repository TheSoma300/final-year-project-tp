from torch import nn
import numpy as np
import torch
from .tp import get_tp_loss

def train_model(model, config, reporter, device, loader, optimizer, epoch):
    model.train()
    reporter.reset_epoch_data()
    for batch_idx, combined_data in enumerate(loader):
        labels = combined_data[-1]
        if config.is_tangent_prop:
            wave_data.requires_grad = True
        data = select_data(combined_data, config)

        n_augs = 1
        if config.model_type == 'segmented': n_augs = len(config.aug_params.get_options_of_chosen_transform())
        
        print(f"n_augs: {n_augs}")
        
        for i in range(n_augs + 1):
            predictions = get_model_prediction(model, data[i], labels, device, config)

            loss, tp_loss, augerino_loss = get_model_loss(predictions, targets, config, device)
            reporter.record_batch_data(predictions, targets, loss)

            # backward
            optimizer.zero_grad()
            loss.backward()

            # gradient descent or adam step
            optimizer.step()
        
        if batch_idx % config.log_interval == 0:
            reporter.keep_log(
                'Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}\t'.format(
                epoch, batch_idx * len(data), len(loader.dataset),
                100. * batch_idx / len(loader), loss.item())
            )
    reporter.record_epoch_data(model, epoch)


def test_model(model, device, loader):
    model.eval()
    

def get_model_prediction(model, data, targets, device, config):
    print(f"data type: {len(data)}")
    print(f"strip type: {len(data[0])}")
    # print(f"strip shape: {data[0].shape}")
    preds_sum = torch.from_numpy(np.zeros((data.shape[0], 10)))
    for i in range(6):
        print(data[0,i].shape)
        strip_data = torch.from_numpy(data[:,i]).to(device=device)
        targets = targets.to(device=device)
        preds = model(strip_data)
        preds_sum += preds
    return preds_sum


def get_model_loss(predictions, targets, config, device, x=None, transformed_data=None):
    base_loss = config.loss(predictions, targets)
    tp_loss = 0
    augerino_loss = 0

    if config.is_tangent_prop:
        tp_loss = config.gamma * get_tp_loss(x, predictions, config.e0, device, transformed_data)
    elif config.augerino:
        augerino_loss = get_aug_loss()
    
    model_loss = base_loss + tp_loss + augerino_loss
    return model_loss, tp_loss, augerino_loss

def init_layer(layer):
    if type(layer) == nn.Conv2d:
        nn.init.kaiming_normal_(layer.weight, mode='fan_out', nonlinearity='relu')

def get_aug_loss():
    return 0

def select_data(combined, conf):
    out = {
        "segmented": combined[2],
        "tp": combined[1],
        "augerino": combined[0]
    }
    return out[conf.model_type]