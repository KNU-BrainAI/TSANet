# -*- coding: utf-8 -*-
"""
Created on Wed Sep  1 15:40:10 2021

Base Within With 10 C 3 Kfold Cross Validation with EEGNet
@author: PC
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data as data_utils
import early_stopping
from early_stopping import EarlyStopping
import numpy as np
import os
import glob
os.environ['KMP_DUPLICATE_LIB_OK']='True'
# mne imports
import mne
from mne import io
from mne.datasets import sample
import math
# tools for plotting confusion matrices
from matplotlib import pyplot as plt

# EEGNet-specific imports
import models
from sklearn.model_selection import train_test_split, LeavePGroupsOut


groups = []
for x in range(1,11):
    for y in range(1,11):
        groups.insert(-1,y)
  
lpgo = LeavePGroupsOut(n_groups=2)

# GPU allocation
save_dir = 'C:/Users/PC/Desktop/TSA_result/EEGNet_Within/3_EEGNet_stacking_10C3CV/'
result_txt = '3_EEGNet_10C3CV_no.txt'
test_result_txt = '3_EEGNet_10C3CV_no_test_result.txt'
##################### Process Main  ######################
for i in range(1,17):
    X = []
    Y =[]
    for filename in glob.glob('C:/Users/PC/Desktop/matlab/dataset/TSA_Raw/seq_sub'+str(i)+'000/*_fr.set'):
        #data path where preprocessed data
        dpath = filename
        print(dpath)
        #get data and find event
        eeglab_raw  = mne.io.read_raw_eeglab(dpath)
        print(eeglab_raw.annotations[1])
        print(len(eeglab_raw.annotations))
        print(set(eeglab_raw.annotations.duration))
        print(set(eeglab_raw.annotations.description))
        print(eeglab_raw.annotations.onset[1])
        anno = mne.read_annotations(dpath)
        print(anno)
        (events_from_annot,event_dict) = mne.events_from_annotations(eeglab_raw)
        print(event_dict)
        print(events_from_annot[:])
        event_id = dict(left=1,right=2)
        tmin = 0
        tmax = 2.9980
        epochs = mne.Epochs(eeglab_raw, events_from_annot, event_id, tmin, tmax,baseline = None)
        labels = epochs.events[:,-1]
        #data *1000 uV to V
        data = epochs.get_data( )*1000000 # format is in (trials, channels, samples)
        X.extend(data)
        Y.extend(labels)
    X=np.array(X)
    Y=np.array(Y)
    print(len(X))
    print(len(Y))
    #samples = 3sec * 512Hz sampling rate
    kernels, chans, samples = 1, 64, 1536
    for fold, (train_index, test_index) in enumerate(lpgo.split(X, Y, groups=groups)):
        X_train = []
        Y_train =[]
        X_validate = []
        Y_validate = []
        X_test = []
        Y_test = []
        X_train_temp = X[train_index]
        Y_train_temp = Y[train_index]
        X_test_temp = X[test_index]
        Y_test_temp = Y[test_index]
        
        
        X_train_split, X_validate_split, Y_train_split, Y_validate_split = train_test_split(X_train_temp, Y_train_temp, train_size=0.7, shuffle=True,
                                                          random_state=1004)
        #overlapping
        print("x_train_split_shape", X_train_split.shape)
        #X_train.extend(X_train_split[:,:,0:1536])
        #Y_train.extend(Y_train_split)
        #X_train.extend(X_train_split[:,:,256:1280])
        #Y_train.extend(Y_train_split)
        #X_train.extend(X_train_split[:,:,512:1536])
        X_train.extend(X_train_split[:,:,:])
        Y_train.extend(Y_train_split)
        X_train=np.array(X_train)
        Y_train=np.array(Y_train)
        print("x_train_shape", X_train.shape)
        
        print("X_validate_split_shape", X_validate_split.shape)
        #X_validate.extend(X_validate_split[:,:,0:1536])
        #Y_validate.extend(Y_validate_split)
        #X_validate.extend(X_validate_split[:,:,256:1280])
        #Y_validate.extend(Y_validate_split)
        #X_validate.extend(X_validate_split[:,:,512:1536])
        X_validate.extend(X_validate_split[:,:,:])
        Y_validate.extend(Y_validate_split)
        X_validate=np.array(X_validate)
        Y_validate=np.array(Y_validate)
        print("X_validate_shape", X_validate.shape)
      
        #X_test.extend(X_test_temp[:,:,0:1024])
        #Y_test.extend(Y_test_temp)
        #X_test.extend(X_test_temp[:,:,256:1280])
        #Y_test.extend(Y_test_temp)
        #X_test.extend(X_test_temp[:,:,512:1536])
        
        X_test.extend(X_test_temp[:,:,:])
        Y_test.extend(Y_test_temp)
        
        X_test=np.array(X_test)
        Y_test=np.array(Y_test)
        print("x_test_shape", X_test.shape)
        
        
        # Numpy array to Tensor
        X_train = torch.Tensor(X_train)
        Y_train = torch.Tensor(Y_train)
        Y_train = F.one_hot(Y_train.to(torch.int64)-1, 2)
        X_validate = torch.Tensor(X_validate)
        Y_validate = torch.Tensor(Y_validate)
        Y_validate = F.one_hot(Y_validate.to(torch.int64)-1, 2)
        X_test = torch.Tensor(X_test)
        Y_test = torch.Tensor(Y_test)
        
        print("xtrian shape:",X_train.shape)
        X_train = X_train.reshape(X_train.shape[0], kernels, chans, samples)
        print("xtrian shape:",X_train.shape)
        X_validate = X_validate.reshape(X_validate.shape[0], kernels, chans, samples)
        X_test = X_test.reshape(X_test.shape[0], kernels, chans, samples)

        print('X_train shape:', X_train.shape)
        print(X_train.shape[0], 'train samples')
        print(X_test.shape[0], 'test samples')

        trn = data_utils.TensorDataset(X_train, Y_train)
        trn_loader = data_utils.DataLoader(trn, batch_size=8, shuffle=True)

        val = data_utils.TensorDataset(X_validate, Y_validate)
        val_loader = data_utils.DataLoader(val, batch_size=8, shuffle=True)

        #################### model training ####################
        criterion = nn.CrossEntropyLoss
        model = models.EEGNet_3_stacking()
        model = model.to('cuda')
        print(model.parameters)
        
        
        
        num_epochs = 100
        trn_loss = []
        val_loss = []
        trn_acc = []
        val_acc = []

        testmodel = model
        savepath = 'C:/Users/PC/PycharmProjects/TSA/testmodel.pth'
        early_stopping = EarlyStopping(patience =100, verbose = True, path = savepath)
        for epoch in range(num_epochs):  # epoch
            model.train()
            avg_loss = 0
            avg_loss2 = 0
            acc = 0
            acc2 = 0
            learning_rate = 0.001*abs(math.cos(epoch)) 
            optimizer = optim.Adam(model.parameters(), lr=learning_rate)
              
            for data_x, data_y in trn_loader: # iteration
                x,y = data_x.to('cuda'), data_y.to('cuda')
                optimizer.zero_grad()
                pred = F.softmax(model(x), dim=1)
                #accuracy
                prediction = torch.max(pred,1)[1]
                y = torch.max(y,1)[1]
                acc += (prediction == y).sum()
                accuracy = acc / len(X_train)
                loss = criterion()(pred, y)
                loss.backward()
                optimizer.step()
                avg_loss += loss / len(trn_loader)
            state = {"state_dict": model.state_dict(), "optimizer": optimizer.state_dict()}
            torch.save(model.state_dict(), savepath)
            model.load_state_dict(torch.load(savepath))

            model.eval()
            with torch.no_grad():
                for data_x, data_y in val_loader:
                    val_x, val_y = data_x.to('cuda'), data_y.to('cuda')
                    pred2 = F.softmax(model(val_x), dim=1)
                    prediction2 = torch.max(pred2,1)[1]
                    val_y = torch.max(val_y,1)[1]
                    loss2 = criterion()(pred2, val_y)
                    avg_loss2 += loss2 / len(val_loader)
                    acc2 += (prediction2 == val_y).sum()
                    accuracy2 = acc2 / len(X_validate)

            print(
                '[Epoch:{}] trn_loss={:.5f}, trn_acc={:.5f}, val_loss={:.5f}, val_acc{:.5f}'.format(epoch + 1, avg_loss,
                                                                                                    accuracy, avg_loss2,
                                                                                                    accuracy2))
            trn_loss.append(avg_loss.item())
            trn_acc.append(accuracy.item())
            val_loss.append(avg_loss2.item())
            val_acc.append(accuracy2.item())
            #early stopping
            early_stopping(avg_loss2, model)

            if early_stopping.early_stop:
                print("Early stopping")
                break
        print("finish training & Validation!")

        plt.plot(trn_acc, 'r')
        plt.plot(trn_loss,'r,--')
        plt.plot(val_acc, 'g')
        plt.plot(val_loss, 'g,--')
        plt.xlabel('epoch')
        plt.title('Subject '+str(i)+" kfold "+str(fold)+' Training & Validation')
        plt.legend(['trn_acc','trn_loss','val_acc','val_loss'])
        plt.savefig(save_dir+'img_no/sub'+str(i)+'/figsub'+str(i)+str(fold)+'.png', dpi=300)
        plt.show()
        model.eval()
        with torch.no_grad():
            Xtest = X_test.to('cuda')
            Ytest = Y_test.to('cuda')
            prob = F.softmax(model(Xtest), dim=1)
            probs = torch.max(prob,1)[1] + 1
            test_acc = 0
            test_acc += (probs == Ytest).sum()
            test_acc2 = test_acc / len(Y_test)
            print("---------------------------------------")
            print("test accuracy={}".format(test_acc2))
        #save test acc to txt files
        f = open(save_dir+result_txt, "a")
        f.write("Sub"+ str(i) + "\n")
        f.write("k =" + str(fold) + "\n")
        f.write("test_acc=" + str(trn_acc[-1]) + "\n")
        f.write("val_acc=" + str(val_acc[-1]) + "\n")
        f.write("test_acc" + str(test_acc2.item()) + "\n")
        f.close()
        f = open(save_dir+test_result_txt, "a")
        f.write(str(test_acc2.item()) + "\n")
        f.close()