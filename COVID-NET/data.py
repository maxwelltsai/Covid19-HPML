import numpy as np
import tensorflow as tf
import tensorflow.keras
import cv2
import os
from sklearn.utils import shuffle
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import pdb
import numpy as np
import sklearn.metrics as sklm



class Metrics(tf.keras.callbacks.Callback):
    def __init__(self, validation_generator):
        
        self.validation_generator = validation_generator
    
    
    def on_epoch_end(self, batch, logs={}):
        self.scores = {
            'recall_score': [],
            'precision_score': [],
            'f1_score': []
        }
    
        for features, y_true in self.validation_generator:
            y_pred = np.asarray(self.model.predict(features))
            y_pred = y_pred.round().astype(int) 
            self.scores['recall_score'].append(sklm.recall_score(y_true[:,0], y_pred[:,0]))
            self.scores['precision_score'].append(sklm.precision_score(y_true[:,0], y_pred[:,0]))
            self.scores['f1_score'].append(sklm.f1_score(y_true[:,0], y_pred[:,0]))
        
        print(f" RC: {np.mean(self.scores['recall_score'])} PR: {np.mean(self.scores['precision_score'])} F1: {np.mean(self.scores['f1_score'])}")
        return
    
class BalanceDataGenerator(tf.keras.utils.Sequence):
    'Generates data for tf.keras'
    def __init__(self,
                 dataset,
                 is_training=True,
                 batch_size=8,
                 input_shape=(512,512),
                 n_classes=3,
                 num_channels=3,
                 mapping={'normal': 0, 'pneumonia': 1, 'COVID-19': 2},
                 shuffle=True,
                 augmentation=True,
                 datadir='data',
                 ):
        'Initialization'
        self.datadir = datadir
        self.dataset = dataset
        self.is_training = is_training
        self.batch_size = batch_size
        self.N = len(self.dataset)
        self.input_shape = input_shape
        self.n_classes = n_classes
        self.num_channels = num_channels
        self.mapping = mapping
        self.shuffle = True

        if augmentation:
            self.augmentation = ImageDataGenerator(
                featurewise_center=False,
                featurewise_std_normalization=False,
                rotation_range=10,
                width_shift_range=0.1,
                height_shift_range=0.1,
                horizontal_flip=True,
                brightness_range=(0.9, 1.1),
                fill_mode='constant',
                cval=0.,
            )

        datasets = {'normal': [], 'pneumonia': [], 'COVID-19': []}
        for l in dataset:
            datasets[l.split()[-1]].append(l)
        self.datasets = [
            datasets['normal'] + datasets['pneumonia'],
            datasets['COVID-19'],
        ]
        print(f"Train: NO-COVID={len(self.datasets[0])}, COVID={len(self.datasets[1])}")

        self.on_epoch_end()


    def __len__(self):
        return int(np.ceil(len(self.datasets[0]) / float(self.batch_size)))

    def on_epoch_end(self):
        'Updates indexes after each epoch'
        if self.shuffle == True:
            for v in self.datasets:
                np.random.shuffle(v)

    def __getitem__(self, idx):
        batch_x, batch_y = np.zeros((self.batch_size, *self.input_shape, self.num_channels)), np.zeros(self.batch_size)

        batch_files = self.datasets[0][idx*self.batch_size : (idx+1)*self.batch_size]
        batch_files[np.random.randint(int(self.batch_size / 4))] = np.random.choice(self.datasets[1])

        for i in range(int(self.batch_size)):
            try:
                sample = batch_files[i].split()
            except Exception as e:
                print(e)
                pdb.set_trace()
            
            if self.is_training:
                folder = 'train'
            else:
                folder = 'test'
            
            
            x = cv2.imread(os.path.join(self.datadir, folder, sample[1]))
            try:
                x = cv2.resize(x, self.input_shape)

            
                if self.is_training and hasattr(self, 'augmentation'):
                    x = self.augmentation.random_transform(x)
    
                    x = x.astype('float32') / 255.0
                    y = self.mapping[sample[2]]
            
                    batch_x[i] = x
                    batch_y[i] = y
            except:
                print(f"Missing {os.path.join(self.datadir, folder, sample[1])}")
                pass

        return batch_x, tf.keras.utils.to_categorical(batch_y, num_classes=self.n_classes)


class DataGenerator(tf.keras.utils.Sequence):
    'Generates data for tf.keras'
    def __init__(self,
                 dataset,
                 is_training=True,
                 batch_size=8,
                 input_shape=(512,512),
                 n_classes=3,
                 num_channels=3,
                 mapping={'normal': 0, 'pneumonia': 1, 'COVID-19': 2},
                 shuffle=True,
                 datadir='data'):
        'Initialization'
        self.dataset = dataset
        self.is_training = is_training
        self.batch_size = batch_size
        self.N = len(self.dataset)
        self.input_shape = input_shape
        self.n_classes = n_classes
        self.num_channels = num_channels
        self.mapping = mapping
        self.shuffle = True
        self.datadir = datadir
        self.on_epoch_end()
        datasets = {'normal': [], 'pneumonia': [], 'COVID-19': []}
        for l in dataset:
            datasets[l.split()[-1]].append(l)

            
        self.datasets = [
            datasets['normal'] + datasets['pneumonia'],
            datasets['COVID-19'],
        ]
        print(f"Test: NO-COVID={len(self.datasets[0])}, COVID={len(self.datasets[1])}")

    def __len__(self):
        return int(np.ceil(self.N / float(self.batch_size)))

    def on_epoch_end(self):
        self.dataset = shuffle(self.dataset, random_state=0)

    def __getitem__(self, idx):
        batch_x, batch_y = np.zeros((self.batch_size, *self.input_shape, self.num_channels)), np.zeros(self.batch_size)
        for i in range(self.batch_size):
            index = min((idx * self.batch_size) + i, self.N-1)

            sample = self.dataset[index].split()

            if self.is_training:
                folder = 'train'
            else:
                folder = 'test'

            x = cv2.imread(os.path.join(self.datadir, folder, sample[1]))
            
            try:
                x = cv2.resize(x, self.input_shape)

                x = x.astype('float32') / 255.0
                #y = int(sample[1])
    
                y = self.mapping[sample[2]]
                
                batch_x[i] = x
                batch_y[i] = y
            except:
                print(f"Missing {os.path.join(self.datadir, folder, sample[1])}")
                pass

        return batch_x, tf.keras.utils.to_categorical(batch_y, num_classes=self.n_classes)