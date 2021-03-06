####
# quick and dirty new version of SLR
# not user friendly or gernralized
# does what I want and thats it
# 20120113 RAT
###


import elasticNetLinReg as enet
from glmnet import glmnet
import numpy as np
import cvTools as st
import regStat



def run(X,y,name):
	nSamp = 100
	alphaList = np.array([1])#np.arange(.1,1.1,.1)
	nObs,nRegs = X.shape
	sdY = np.sqrt(np.var(y))
	# selection via bootstrap
	bestMin = 1E10
	for a in alphaList:
		tmpErr,tmpEnm,allVals = fitSampling(X,y,a,nSamp,method='bs')
		tmpErrV = tmpErr.mErr
		tmpMin = np.min(tmpErrV)
		print tmpMin
		
		if tmpMin < bestMin:
			bestMin = tmpMin
			modelIndex = np.argmin(tmpErrV)
			enm = tmpEnm
			err = tmpErr
			alpha = a
	
	# important values
	lam = enm.lambdas[modelIndex]
	yHat = enm.predict(X)[:,modelIndex]
	intercept = enm.intercept[modelIndex]
	globalCoef = enm.coef[np.abs(enm.coef[:,modelIndex])>1E-21,modelIndex]
	coefIndex = enm.indices[np.abs(enm.coef[:,modelIndex])>1E-21]
	notEmpty = len(coefIndex) > 0
	

	# get the bootstrap residual response samples
	res = y - yHat
	resCent = res-np.mean(res)
	ySample = np.zeros((nObs,nSamp))
	for i in range(nSamp):
		resSample = st.sampleWR(resCent)
		ySample[:,i] = yHat+resSample


	notEmpty = len(coefIndex) > 0

	if notEmpty:
		# working on subset now
		Xhat = X[:,coefIndex]
		nObs,nRegsHat = Xhat.shape
		sdXhat = np.sqrt(np.var(Xhat,0))

		
		# residual bs time
		sumErr = 0
		sumSqErr = 0
		sumNullErr = 0
		sumSqNullErr = 0
		sc = np.zeros(nRegsHat)
		sSqc = np.zeros(nRegsHat)
		sumSup = np.zeros(nRegsHat)

		for i in range(nSamp):
			# cv to get the errors
			err,tmpEnm,tmpallVals = fitSampling(Xhat,ySample[:,i],alpha,10,method='cv',lambdas=[lam])
			sumErr = err.mErr[0] + sumErr
			sumSqErr = err.mErr[0]**2 + sumSqErr
			# cv over this thing to get the null model errors
			nullErr,a = fitSamplingNull(ySample[:,i],10, method='cv')
			sumNullErr = sumNullErr + nullErr
			sumSqNullErr = sumSqNullErr + nullErr**2
			# need the coef
			# they change so we need to map the back to the original
			tmpEnm = enet.fit(Xhat,ySample[:,i], alpha,lambdas=[lam])
			sc[tmpEnm.indices] = sc[tmpEnm.indices] + tmpEnm.coef[:,0]
			sSqc[tmpEnm.indices] = sSqc[tmpEnm.indices] + tmpEnm.coef[:,0]**2
			# find supports 
			occur = np.zeros(len(tmpEnm.coef[:,0]))
			occur[abs(tmpEnm.coef[:,0])>1E-25] = 1.0
			sumSup[tmpEnm.indices] = sumSup[tmpEnm.indices] + occur
				

		# get averages and variances
		aveErr = sumErr/nSamp
		sdErr = np.sqrt(sumSqErr/nSamp - aveErr**2)
		aveNullErr = sumNullErr/nSamp
		sdNullErr = np.sqrt(sumSqNullErr/nSamp - aveNullErr**2)
		aveCoef = sc/nSamp
		sdCoef = np.sqrt(sSqc/nSamp - aveCoef**2)
		pSup = sumSup/nSamp

		
		# let do the leave one out importance deal
		codN = np.zeros(nRegsHat) 
		if nRegsHat>1:
			for j in range(nRegsHat):
				Xprime = np.delete(Xhat,j,axis=1)

				# residual bs time
				sumErr = 0
				sumSqErr = 0
				
				for i in range(nSamp):
					# cv to get the errors
					err,tmpenm,tmpallVals = fitSampling(Xprime,ySample[:,i],alpha,10,method='cv',lambdas=[lam])
					sumErr = err.mErr[0] + sumErr
					sumSqErr = err.mErr[0]**2 + sumSqErr

				codN[j] = sumErr/nSamp

		elif nRegsHat==1:
			codN[0] = aveNullErr

		# lets do leave only one
		cod1 = np.zeros(nRegsHat) 
		for j in range(nRegsHat):
			Xprime = np.zeros((nObs,1))
			Xprime[:,0] = Xhat[:,j]

			# residual bs time
			sumErr = 0
			sumSqErr = 0
			
			for i in range(nSamp):
				# cv to get the errors
				err,tmpenm,tmpallVals = fitSampling(Xprime,ySample[:,i],alpha,10,method='cv',lambdas=[lam])
				sumErr = err.mErr[0] + sumErr
				sumSqErr = err.mErr[0]**2 + sumSqErr

			cod1[j] = sumErr/nSamp


		# now we are going to estimate
		# some pvalues.  it should
		# be noted: that we want to use
		# permutation, to get a real feel
		# for random or unrelated data 
		# but we dont want to run a bs
		# for each perm (but we should)
		# so in here we are using the 
		# ols stderr to get the test stat
		# we will record a bunch of stuff 
		# from here to look at latter
		p,tStat,tStatPerm,olsSE = regStat.netTTestPermute(Xhat,y,lam,alpha,nperm=1000)
		n,m = tStatPerm.shape
		#*****
		# would like to check if any values are nan
		# this most likly means the gpd failed in goodness of fit for tail
		# will use direct permutation values as the estimate in that case 
		# *** some other form of automated checking might be good here
		for i in range(n):
			if np.isnan(p[i]):
				z = tStatPerm[i,:]
				tmp = np.sum(z>tStat[i]) 
				p[i] = float(tmp)/float(m)
	else:
		
			# residual bs time
		sumNullErr = 0
		sumSqNullErr = 0
		
		for i in range(nSamp):
			# cv over this thing to get the null model errors
			nullErr,a = fitSamplingNull(ySample[:,i],10, method='cv')
			sumNullErr = sumNullErr + nullErr
			sumSqNullErr = sumSqNullErr + nullErr**2
		
		# get averages and variances
		aveNullErr = sumNullErr/nSamp
		sdNullErr = np.sqrt(sumSqNullErr/nSamp - aveNullErr**2)
		aveErr = aveNullErr
		sdErr = sdNullErr
	
	


	# we have it all, lets print it
	f = open('SLR2run_'+name+'.dat','w')
	
	lam.tofile(f,sep="\t")
	f.write("\n")
	
	alpha.tofile(f,sep="\t")
	f.write("\n")
	
	intercept.tofile(f,sep="\t")
	f.write("\n")	

	aveErr.tofile(f,sep="\t")
	f.write("\n")

	sdErr.tofile(f,sep="\t")
	f.write("\n")

	aveNullErr.tofile(f,sep="\t")
	f.write("\n")

	sdNullErr.tofile(f,sep="\t")
	f.write("\n")
	
	sdY.tofile(f,sep="\t")
	f.write("\n")
	
	if notEmpty:

		coefIndex.tofile(f,sep="\t")
		f.write("\n")
	
		sdXhat.tofile(f,sep="\t")
		f.write("\n")

		globalCoef.tofile(f,sep="\t")
		f.write("\n")
		
		aveCoef.tofile(f,sep="\t")
		f.write("\n")

		sdCoef.tofile(f,sep="\t")
		f.write("\n")

		pSup.tofile(f,sep="\t")
		f.write("\n")

		codN.tofile(f,sep="\t")
		f.write("\n")

		cod1.tofile(f,sep="\t")
		f.write("\n")

		p.tofile(f,sep="\t")
		f.write("\n")

		olsSE.tofile(f,sep="\t")
		f.write("\n")


	f.close()


	

	

			












		
	


def fitSampling(regressors, response, alpha, nSamp, method='cv', 
		memlimit=None, largest=None, **kwargs):
	"""Performs an elastic net constrained linear regression,
	see fit, with selected sampleing method to estimate errors
	using nSamp number of sampleings.
	methods:
	'cv'	cross validation with nSamp number of folds
	'bs'	bootstrap 
	'bs632'	boostrap 632 (weighted average of bs and training error)
	Returns a TrainingError object (cvTools) and an 
	ENetModel object for the full fit (err,enm).
	Function requires cvTools
	"""
	
	nObs,nRegs = regressors.shape
	# get the full model fit 
	fullEnm = enet.fit(regressors, response, alpha, memlimit,
                largest, **kwargs)
	# get the lambda values determined in the full fit (going to force these lambdas for all cv's)
	lam = fullEnm.lambdas
	# the lambdas may have been user defined, don't want it defined twice 
	if kwargs.has_key('lambdas'):
		del kwargs['lambdas']

	# lets partition the data via our sampling method
	if method=='cv':
		t,v = st.kFoldCV(range(nObs),nSamp,randomise=True)
	elif (method=='bs') or (method=='bs632'):
		t,v = st.kRoundBS(range(nObs),nSamp)
	else:
		raise ValueError('Sampling method not correct')

	# lets consider many versions of errors
	# with our error being mean squared error
	# we want the epected mean squared error
	# and the corisponding variance over the diffrent versions
	nModels = len(lam)
	smse = np.zeros(nModels)
	sSqmse = np.zeros(nModels)
	allVals = np.zeros((nModels,nSamp))

		# loop through the folds
	for i in range(nSamp):
		# get the training values
		X = regressors[t[i]]
		y = response[t[i]]
		enm =  enet.fit(X, y, alpha, memlimit,
                	largest, lambdas=lam, **kwargs)
			# get the validation values
		Xval = regressors[v[i]]
		Yval = response[v[i]]
		nVal = float(len(Yval))
		# get the predicted responses from validation regressors
		Yhat = enm.predict(Xval)
				# what is the mean squared error?
		# notice the T was necassary to do the subtraction
		# the rows are the models and the cols are the observations
		mse = np.sum((Yhat.T-Yval)**2,1)/nVal
		# sum the rows (errors for given model)
		smse = smse + mse
		sSqmse = sSqmse + mse**2
		allVals[:,i] = mse
		
	# now it is time to average and send back
	# I am putting the errors in a container 
	nSampFlt = float(nSamp)
	meanmse = smse/nSampFlt
	varmse = sSqmse/nSampFlt - meanmse**2
	if method=='bs632':
		yhat = fullEnm.predict(regressors)
		resubmse = np.sum((yhat.T-response)**2,1)/float(nObs)
		meanmse = 0.632*meanmse+(1-0.632)*resubmse
		
	err = enet.ENetTrainError(lam,nSamp,meanmse,varmse,[0],[0],alpha)
	err.setParamName('lambda')

	fullEnm.setErrors(err.mErr)
	
	return err, fullEnm, allVals 
	
	



def fitSamplingNull(response,nSamp, method='cv', 
		memlimit=None, largest=None, **kwargs):
	nObs = len(response)
	# lets partition the data via our sampling method
	if method=='cv':
		t,v = st.kFoldCV(range(nObs),nSamp,randomise=True)
	elif (method=='bs') or (method=='bs632'):
		t,v = st.kRoundBS(range(nObs),nSamp)
	else:
		raise ValueError('Sampling method not correct')

	smse = 0
	sSqmse = 0

	for i in range(nSamp):
		# get the training values
		
		y = response[t[i]]
		Yval = response[v[i]]
		nVal = float(len(Yval))
		mse = np.sum((Yval-np.mean(y))**2)/nVal
		# sum the rows (errors for given model)
		smse = smse + mse
		sSqmse = sSqmse + mse**2
		
	# now it is time to average and send back
	# I am putting the errors in a container 
	nSampFlt = float(nSamp)
	meanmse = smse/nSampFlt
	varmse = sSqmse/nSampFlt - meanmse**2
	if method=='bs632':
		yhat = fullEnm.predict(regressors)
		resubmse = np.sum((yhat.T-response)**2,1)/float(nObs)
		meanmse = 0.632*meanmse+(1-0.632)*resubmse
		
	return meanmse, varmse


