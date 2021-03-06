from tpot import TPOTClassifier
import glob
import os
import shutil
# from shutil import copyfile
from pprint import pprint
import pickle
from PIL import Image
import numpy as np
from autoPyTorch import AutoNetClassification, HyperparameterSearchSpaceUpdates
import sklearn.model_selection
import sklearn.metrics
from sklearn import preprocessing
import torch
from torch.autograd import Variable
from torchvision import transforms
import json
from sklearn.externals.joblib import Parallel, delayed
from dask.distributed import Client
from xgboost import XGBClassifier
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix



input_size = (256, 256)
channels = 1
balance = 280 #Examples / class, set None if you want to load all examples
final_dataset_location = "/tmp/covid_dataset"
initial_dataset_location = "../data"
classes = ["covid", "Pneumonia", "No Finding"]
preset = "full_cs"
save_output_to = "/tmp/{2}class_{1}balanced_ba_ce_{0}_{3}".format(input_size[0], balance, len(classes), preset)



def get_references(images = [] , labels = [] , filter = "_positive.txt", copy_to = final_dataset_location, copy_from = initial_dataset_location, balance = balance, classes = classes, img_channels = channels):
    '''
    If you don't  want to copy set copy_to = None; only if this is set img_channels is taken into account 
    balance = 180 means each class gets 180 examples before splits
    '''
    for name in glob.glob(initial_dataset_location + os.path.sep + "*{}".format(filter)):
        class_name = name.split(filter)[0].split("/")[-1].lower()
        if any(class_name in s.lower() for s in classes):
            for i, imagepaths in enumerate(open(name).readlines()):
                if i==balance:
                    break
                images.append(imagepaths)
                labels.append(class_name)
    # le = preprocessing.LabelBinarizer()
    le = preprocessing.LabelEncoder()
    le.fit(list(set(labels)))
    #Create sklearn type labels
    labels = le.transform(labels)
    print("Found {} examples with labels {}".format(len(labels), le.classes_))
    assert len(labels) > 0, "No data found"
    #Copy data locally and preprocess
    if copy_to:
        os.makedirs(copy_to, exist_ok=True)
        for i, im in enumerate(images):
            if "\n" in im:
                im = im.strip()
            if img_channels == 3:
                mode = "RGB"
            elif img_channels == 1:
                mode = "L"
            with Image.open(im).convert(mode) as image:
                image = image.resize(input_size)
                im_arr = np.fromstring(image.tobytes(), dtype=np.uint8) / 255.0
            try:
                im_arr = im_arr.reshape((image.size[1], image.size[0], img_channels))
            except ValueError as e:
                im_arr = im_arr.reshape((image.size[1], image.size[0]))
                im_arr = np.stack((im_arr,) * img_channels, axis=-1)
            finally:
                im_arr = np.moveaxis(im_arr, -1, 0) #Pytorch is channelfirst
                dest = os.path.join(copy_to, "{0}_{2}.{1}".format(str(i), im.split("/")[-1].split(".")[-1], "-".join(le.inverse_transform(labels)[i].split(" "))))
                # copyfile(im, dest)
                image.save(dest) 
                # print("Wrote image {} of shape {} with label {}({})".format(dest, im_arr.shape, labels[i], le.inverse_transform(labels)[i]))
            images[i] = dest
        print("Copy {} files".format(i+1))
    assert len(images) == len(labels)
    return images, labels, le


def image_loader_torch(image_path):
    """load image, returns cuda tensor"""
    image = Image.open(image_path)
    image = loader(image).float()
    image = Variable(image, requires_grad=True)
    image = image.unsqueeze(0)  #this is for VGG, may not be needed for ResNet
    return image.cuda()  #assumes that you're using GPU


def image_to_array(image_path):
    """
    Loads JPEG imag
    """
    with Image.open(image_path).convert("RGB") as image:
        image = image.resize(input_size)
        im_arr = np.fromstring(image.tobytes(), dtype=np.uint8) / 255.0
        try:
            im_arr = im_arr.reshape((image.size[1], image.size[0], 3))
        except ValueError as e:
            im_arr = im_arr.reshape((image.size[1], image.size[0]))
            im_arr = np.stack((im_arr,)*3, axis=-1)
    return im_arr


def predict(network, test_loader, device, move_network=True):
    """ predict batchwise """
    # Build DataLoader
    if move_network:
        network = network.to(device)

    # Batch prediction
    network.eval()
    Y_batch_preds = list()
    
    for i, (X_batch, Y_batch) in enumerate(test_loader):
        # Predict on batch
        X_batch = Variable(X_batch).to(device)
        batch_size = X_batch.size(0)

        Y_batch_pred = network(X_batch).detach().cpu()
        Y_batch_preds.append(Y_batch_pred)
    
    return torch.cat(Y_batch_preds, 0)


# def read_images(image_paths_list, parallel_threads):
#   from scipy.misc import imread, imsave
#   images = Parallel(n_jobs=parallel_threads, verbose=5)\
#         (delayed(imread)(f) for f in image_paths_list)
#   return images


def create_model(max_batch):
    search_space_updates = HyperparameterSearchSpaceUpdates()
    #TODO: this still runs out of memory and wastes resources
    search_space_updates.append(node_name="CreateImageDataLoader", hyperparameter="batch_size", log=False, \
                                value_range=[2, max_batch]) 
    try:
        shutil.rmtree(save_output_to)
    except FileNotFoundError as e:
        pass
    autonet = AutoNetClassification(
                                    preset, \
                                    # hyperparameter_search_space_updates=search_space_updates, \
                                    min_workers=2, \
                                    # dataloader_worker=4, \
                                    # global_results_dir="results", \
                                    # keep_only_incumbent_checkpoints=False, \
                                    log_level="info", \
                                    budget_type="time", \
                                    # save_checkpoints=True, \
                                    result_logger_dir=save_output_to, \
                                    min_budget=200, \
                                    max_budget=600, \
                                    num_iterations=1, \
                                    # images_shape=[channels, input_size[0], input_size[1]], \
                                    optimizer = ["adam", "adamw", "sgd", "rmsprop"], \
                                    algorithm="hyperband", \
                                    optimize_metric="balanced_accuracy", \
                                    additional_metrics=["pac_metric"], \
                                    lr_scheduler=["cosine_annealing", "cyclic", "step", "adapt", "plateau", "alternating_cosine", "exponential"], \
                                    networks=['mlpnet', 'shapedmlpnet', 'resnet', 'shapedresnet'], #, 'densenet_flexible', 'resnet', 'resnet152', 'darts'], \
                                    use_tensorboard_logger=True, \
                                    cuda=True \
                                    )
    return autonet


if __name__ == "__main__":
    images, labels, le  = get_references()

    # model = create_model(max_batch=int(len(labels)/20)) #Lipschitz magical number
    X = []
    for i, im in enumerate(images):
        image = image_to_array(im)
        X.append(image)
    #autopytorch format
    X = np.asarray([np.asarray(x).flatten() for x in X])
    labels = np.asarray(labels)
    X_train, X_test, y_train, y_test = sklearn.model_selection.train_test_split(X, labels, test_size=0.1, random_state=9, shuffle=True)
    print("Starting TPOT")
    # tpot = TPOTClassifier(generations=5, population_size=50, verbosity=2, n_jobs=40, random_state=42, use_dask=True)
    # tpot.fit(X_train, y_train)
    # print(tpot.score(X_test, y_test))
    # tpot.export('tpot_iris_pipeline.py')

    exported_pipeline = XGBClassifier(learning_rate=0.01, max_depth=9, min_child_weight=2, n_estimators=100, nthread=40, subsample=0.7000000000000001)

    exported_pipeline.fit(X_train, y_train)
    results = exported_pipeline.predict(X_test)

    print(classification_report(y_test, results, target_names=le.classes_))
    print(confusion_matrix(y_test, results, labels=range(3)))
