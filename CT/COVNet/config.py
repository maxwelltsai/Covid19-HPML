import argparse


def parse_arguments():
    """Argument Parser for the commandline argments
    :returns: command line arguments

    """
    ##########################################################################
    #                            Training setting                            #
    ##########################################################################
    parser = argparse.ArgumentParser()
    parser.add_argument('--lr', type=float, default=1e-5)
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--lr_scheduler', type=str, default='plateau', choices=['plateau', 'step'])
    parser.add_argument('--data_augment', action='store_true', help='Apply data augmentation')
    parser.add_argument('--patience', type=int, default=9)
    parser.add_argument('--log-every', type=int, default=10)
    parser.add_argument('--save-model', type=bool, default=True)
    args = parser.parse_args()

    return args
