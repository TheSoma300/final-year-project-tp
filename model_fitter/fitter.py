from .dataset import *
from .utils import *
from .utils import GaussianNoiseAug, PitchShiftAug, AugAveragedModel
import time
import torch.nn as nn
from torch.utils.data import DataLoader
import torchaudio.transforms as aud_transforms
import gc

class ModelFitter:
    def __init__(self, args, model_config, device, kwargs, reporter):
        self.args = args
        self.model_config = model_config
        self.device = device
        self.kwargs = kwargs
        self.reporter = reporter


    def fit(self): 
        model, optimizer = self.init_model()
        train_loader, test_loader, metadata = self.get_data_loaders()

        self.reporter.train_set_len = len(train_loader.dataset)
        all_predictions, all_targets = None, None
        for epoch in range(self.model_config.epochs):
            train_model(model, self.model_config, self.reporter, self.device, train_loader, optimizer, epoch)
            all_predictions, all_targets = test_model(model, self.model_config, self.reporter, self.device, test_loader, epoch)
            self.reporter.record_epoch_data(epoch)
            
            if (epoch + 1) % self.model_config.log_interval == 0:
                self.reporter.save_model(model, epoch)
                self.reporter.save_metrics(epoch)
                self.reporter.save_predictions_for_cm(all_predictions, all_targets, epoch)
            
            gc.collect()
            torch.cuda.empty_cache()
        self.reporter.save_model(model, 'final')
        self.reporter.save_metrics('final')
        self.reporter.save_predictions_for_cm(all_predictions, all_targets, 'final')



    def get_data_loaders(self):
        print("Loading in data...")
        
        GTZAN = load_path_data(
            self.args.data_path,
            test_size=self.model_config.test_size,
            is_local=self.args.local
        )
        train_loader = DataLoader(
            GtzanDynamicDataset(
                paths           = GTZAN.train_x,
                labels          = GTZAN.train_y,
                mel_spec_params = self.model_config.dataset_params,
                aug_params      = self.model_config.aug_params,
                device          = self.device,
                train           = True,
                model_type        = self.model_config.model_type
            ), 
            batch_size=self.model_config.batch_size,
            shuffle=True
        )

        test_loader = DataLoader(
            GtzanTTADataset(
                paths           = GTZAN.test_x,
                labels          = GTZAN.test_y,
                mel_spec_params = self.model_config.dataset_params,
                aug_params      = self.model_config.aug_params,
                device          = self.device,
                train           = False,
                tta_settings    = self.model_config.tta_settings[self.model_config.aug_params.transform_chosen]
            ),
            batch_size=self.model_config.batch_size,
            shuffle=False
        )
        self.reporter.keep_log(str(GTZAN.get_metadata()))
        return train_loader, test_loader, GTZAN.get_metadata()

    def init_model(self):
        if self.model_config.augerino:
            return self.init_augerino_model()
        out_model = self.model_config.model().to(device=self.device, dtype=torch.float32)
        out_model.apply(init_layer)
        
        out_optimizer = self.model_config.optimizer(out_model.parameters(), weight_decay=self.model_config.weight_decay, lr=self.model_config.lr)
        return out_model, out_optimizer

    def init_augerino_model(self):
        net = self.model_config.model().to(device=self.device, dtype=torch.float32)
        net.apply(init_layer)

        aug = None
        if self.model_config.aug_params.transform_chosen == 'ps': aug = PitchShiftAug()
        elif self.model_config.aug_params.transform_chosen == 'ni': aug = GaussianNoiseAug()
        else: 
            raise RuntimeError('no augmentation for augerino... a bit counterintuitive dont u think?')

        aug = aug.to(device=self.device)
        self.model_config.model = AugAveragedModel(net, aug, get_model_prediction, self.device).to(device=self.device)

        out_optimizer = self.model_config.optimizer(self.model_config.model.parameters(), lr=self.model_config.lr)
        return self.model_config.model, out_optimizer

