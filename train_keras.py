import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ReduceLROnPlateau
import tensorflow.keras
from model import build_COVIDNet
import pdb
import numpy as np
import os, pathlib, argparse
import cv2
from sklearn.metrics import confusion_matrix
from data import DataGenerator, BalanceDataGenerator, Metrics

os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3'  # which gpu to train on

# TO-DO: add argparse when converting to script
parser = argparse.ArgumentParser(description='COVID-Net Training')
parser.add_argument('--trainfile', default='train_COVIDx.txt', type=str, help='Name of train file')
parser.add_argument('--testfile', default='test_COVIDx.txt', type=str, help='Name of test file')
parser.add_argument('--data_path', default='data', type=str, help='Path to data folder')
parser.add_argument('--lr', default=0.00002, type=float, help='Learning rate')
parser.add_argument('--img_size', type=int, default=512, help='Image size to use')
parser.add_argument('--bs', default=8, type=int, help='Batch size')
parser.add_argument('--epochs', default=10, type=int, help='Number of epochs')
parser.add_argument('--name', default='COVIDNet', type=str, help='Name of training folder')
parser.add_argument('--checkpoint', default='', type=str, help='Start training from existing weights')
parser.add_argument('--model', default='resnet50v2', type=str, help='Start training with model specification')
 
args = parser.parse_args()
print(args)

mapping = {'normal': 0, 'pneumonia': 1, 'COVID-19': 2}
class_weight = {0: 1., 1: 1., 2: 25.}
num_classes = 3
batch_size = args.bs
epochs = args.epochs
lr = args.lr
outputPath = './output/'
runID = args.name + 'lr' + str(lr)
runPath = outputPath + runID
pathlib.Path(runPath).mkdir(parents=True, exist_ok=True)
print('Output: ' + runPath)

# load data
file = open(args.trainfile, 'r')
trainfiles = file.readlines()
file = open(args.testfile, 'r')
testfiles = file.readlines()

train_generator = BalanceDataGenerator(trainfiles, input_shape=(args.img_size,args.img_size), datadir=args.data_path, is_training=True)
test_generator = DataGenerator(testfiles, input_shape=(args.img_size,args.img_size), datadir=args.data_path, is_training=False)


def get_callbacks(runPath):
    callbacks = []
    lr_schedule = ReduceLROnPlateau(monitor='val_loss', factor=0.7, patience=5, min_lr=0.000001, min_delta=1e-2)
    callbacks.append(lr_schedule) # reduce learning rate when stuck

    checkpoint_path = runPath + '/cp-{epoch:02d}-{val_loss:.2f}.hdf5'
    callbacks.append(tf.keras.callbacks.ModelCheckpoint(checkpoint_path,
        verbose=1, save_best_only=False, save_weights_only=True, mode='min', period=1))

    class SaveAsCKPT(tf.keras.callbacks.Callback):
        def __init__(self):
            self.saver = tf.train.Saver()
            self.sess = tf.keras.backend.get_session()

        def on_epoch_end(self, epoch, logs=None):
            checkpoint_path = runPath + '/cp-{:02d}.ckpt'.format(epoch)
            save_path = self.saver.save(self.sess, checkpoint_path)
    callbacks.append(SaveAsCKPT())
    
    metrics = Metrics(validation_generator=test_generator)
    callbacks.append(metrics)
    callbacks.append(tf.keras.callbacks.TensorBoard(log_dir=checkpoint_path))

    return callbacks

model = build_COVIDNet(checkpoint=args.checkpoint,args=args)

opt = Adam(learning_rate=lr, amsgrad=True)
callbacks = get_callbacks(runPath)
model.compile(loss='categorical_crossentropy',
              optimizer=opt,
              metrics=['accuracy']) # TO-DO: add additional metrics for COVID-19
print('Ready for training!')

model.fit_generator(train_generator, 
                    callbacks=callbacks, 
                    validation_data=test_generator, 
                    epochs=epochs, 
                    shuffle=True, 
                    class_weight=class_weight, 
                    use_multiprocessing=True,
                    steps_per_epoch=4)

y_test = []
pred = []
for i in range(len(testfiles)):
    line = testfiles[i].split()
    x = cv2.imread(os.path.join(args.data_path, 'test', line[1]))
    x = cv2.resize(x, (args.img_size, args.img_size))
    x = x.astype('float32') / 255.0
    y_test.append(mapping[line[2]])
    pred.append(np.array(model.predict(np.expand_dims(x, axis=0))).argmax(axis=1))
y_test = np.array(y_test)
pred = np.array(pred)

matrix = confusion_matrix(y_test, pred)
matrix = matrix.astype('float')
print(matrix)
class_acc = [matrix[i,i]/np.sum(matrix[i,:]) if np.sum(matrix[i,:]) else 0 for i in range(len(matrix))]
print('Sens Normal: {0:.3f}, Pneumonia: {1:.3f}, COVID-19: {2:.3f}'.format(class_acc[0],
                                                                           class_acc[1],
                                                                           class_acc[2]))
ppvs = [matrix[i,i]/np.sum(matrix[:,i]) if np.sum(matrix[:,i]) else 0 for i in range(len(matrix))]
print('PPV Normal: {0:.3f}, Pneumonia {1:.3f}, COVID-19: {2:.3f}'.format(ppvs[0],
                                                                         ppvs[1],
                                                                         ppvs[2]))