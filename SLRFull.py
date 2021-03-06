###########
# Created to run a spares linear regression analysis.
# Methods that perform elastic-net (lasso) regression,
# uses bootstrap sampling for penalty selection,
# uses bootstrap residual for determining statistic distributions
# uses permutation analysis to determine null distribution,
# estimates importance by a single step forward and backward
# selection.  Other than importance the full feature matrix is 
# used in all estimates of statistics.
#
# Created 20120330 RAT
#
###########
import elasticNetLinReg as enet
from glmnet import glmnet
import numpy as np
import math
import gpdPerm
import cvTools as st
import SLR2
from scipy.sparse import lil_matrix


def run(X,y,name,nSamp=100,nPerms=1000,alphaList=np.array([1])):
	""" Run the full estimation / permutation routine 
	and then save the data to a file.
	"""
	if nPerms>0:
		solution, enm = permModel(X,y,nSamp,alphaList,nPerms,reselect=False)
	else:
		solution, enm = estModel(X,y,nSamp,alphaList,estImp=True)

	# we use the stDev latter so lets just get it now
	solution['sdY'] = np.sqrt(np.var(y))
	nObs,nRegs = X.shape
	sdX = np.zeros(nRegs)
	sdX[solution['indices']] = np.sqrt(np.var(X[:,solution['indices']],0))
	solution['sdX'] = sdX


	# we have it all, lets print it	
	
	f = open(name,'w')
	
	enm.lambdas[0].tofile(f,sep="\t")
	f.write("\n")
	
	enm.alpha.tofile(f,sep="\t")
	f.write("\n")

	enm.intercept[0].tofile(f,sep="\t")	
	f.write("\n")

	solution['aveErr'].tofile(f,sep="\t")
	f.write("\n")

	solution['sdErr'].tofile(f,sep="\t")
	f.write("\n")

	solution['aveNullErr'].tofile(f,sep="\t")
	f.write("\n")

	solution['sdNullErr'].tofile(f,sep="\t")
	f.write("\n")
	
	solution['sdY'].tofile(f,sep="\t")
	f.write("\n")	
	
	ind = solution['indices']

	if len(ind)>0:
		ind.tofile(f,sep="\t")
		f.write("\n")
	
		solution['sdX'][ind].tofile(f,sep="\t")
		f.write("\n")

		# need to get the coefs
		coef = np.zeros(nRegs)
		# note due to the bs residual, we may have 
		# non zero means for coefs with a zero global 
		# value, so lets set that up.
		coef[enm.indices] = enm.coef
		coef[ind].tofile(f,sep="\t")
		f.write("\n")
		
		solution['medCoef'][ind].tofile(f,sep="\t")
		f.write("\n")

		solution['sdCoef'][ind].tofile(f,sep="\t")
		f.write("\n")

		solution['pSup'][ind].tofile(f,sep="\t")
		f.write("\n")

		solution['errOut'][ind].tofile(f,sep="\t")
		f.write("\n")

		solution['errIn'][ind].tofile(f,sep="\t")
		f.write("\n")

		
		if nPerms > 0:
			solution['p'][ind].tofile(f,sep="\t")
			f.write("\n")



	f.close()




def permModel(X,y,nSamp=100,alphaList=np.array([1]),nPerms=1000,reselect=False):
	"""This does it all folks, runs the full model 
	with bs samp for model selection, at the selected model 
	runs the bs res on the full feature set X
	to estimate the sdDev and means for various values 
	(ie coef), while doing that it uses 10 fold CV at each 
	sample to estimate prediction errors.  It then does all
	of that nPerms time to do a full permutation analysis,
	and uses these values to estimate tStats and finaly 
	p-values for the coef (this is imporved, when possible,
	by using the GPD approx.  Also we estimate importance 
	scores for the various coef, but this is not done over
	the random permutations.  If reselect then the bs 
	selection process is reimplimented at each permutation
	otherwise model selected on non permuted values is 
	used.
	"""
	nObs,nRegs = X.shape
	solution, enm = estModel(X,y,nSamp,alphaList,estImp=True)
	medCoef = solution['medCoef']
	aveCoef = solution['aveCoef']
	sdCoef = solution['sdCoef']
	indices = solution['indices']
	lam = enm.lambdas[0]
	alpha = enm.alpha
	p = np.ones(nRegs)
	if len(indices)>0:
		sdCoef[sdCoef<1E-21] = 1E-21
		tStat = np.abs(medCoef/sdCoef)
		tStatPerm = lil_matrix((nRegs,nPerms))
		for i in range(nPerms):
			# permute the response 
			# *** probably should keep track to avoid repeats, future???
			yPerm = np.random.permutation(y)
			if reselect:
				solutionPerm, _= estModel(X,yPerm,nSamp,alphaList,estErr=False)
			else:
				solutionPerm, _= estModel(X,yPerm,nSamp,alphaList,estErr=False,params=(lam,alpha))
			medCoefPerm = solutionPerm['medCoef']
			sdCoefPerm = solutionPerm['sdCoef']
			indPerm = solutionPerm['indices']
			
			if len(indPerm)>0:
				sdCoefPerm[sdCoefPerm<1E-21] = 1E-21
				tmp = np.abs(medCoefPerm/sdCoefPerm)
				# more crzy shift cuz the dif from 1-d array in np and scipy
				tStatPerm[indPerm,i] = np.array(tmp[indPerm],ndmin=2).T 
		#np.savetxt('tStat.dat',tStat)
		#np.savetxt('tStatPerm.dat',np.array(tStatPerm.todense()))		


		# no values should have 2 in the end,
		# this will let us know if something goes wrong
		p = np.ones(nRegs)
		for i in range(nRegs):
			# even more confusion for scpy and np arrays
			# gdpPerm is expecting a vector which is diffrent 
			# from an nx1 matrix (apperently) 
			curTStatPerm = np.array(tStatPerm[i,:].todense())[0,:]
			p[i] = gpdPerm.est(tStat[i],curTStatPerm)
			# use standard permutation if this fails 
			if np.isnan(p[i]) or p[i] < 1E-21:
				tmp = np.sum(curTStatPerm>=tStat[i])+1
				p[i] = float(tmp)/(float(nPerms))
				if p[i]>1.0:p[i]=1.0

	solution['p'] = p
	return solution, enm



def estModel(X,y,nSamp=100,alphaList=np.array([1]),estErr=True,estImp=False,params=[]):
	"""Estimate a mean and standard deviation
	for an elastic net model using bootstrap 
	residual.
	Note: Bootstrap resampling is used to select
	model parameters, then the bs res at these 
	params is used on the full feature set X
	to calculate means and standard errors.
	Note: if estErr then 10 fold CV is used to estimate 
	the prediction error at each iteration of the bs.
	This is ten extra iterations at each bs res 
	sample, but reduces the bias in prediction error.
	The mean and sdDev of the CV error is then reported.
	Note: If params are passed then we assume its a tuple
	with the (lambda,alpha) model parameters.  In this case 
	model selection is bipassed. and these params are used.
	"""

	nObs,nRegs = X.shape
	# select full model values
	if len(params)==2:
		lam,alpha = params
		enm = enet.fit(X,y,alpha,lambdas=[lam])[0]
	else:
		enm = select(X,y,nSamp,alphaList)
	lam = enm.lambdas[0]
	yHat = enm.predict(X)
	intercept = enm.intercept[0]
	globalCoef =enm.coef[np.abs(enm.coef)>1E-21]
	coefIndex = enm.indices[np.abs(enm.coef)>1E-21]
	alpha = enm.alpha

	# get the bootstrap residual response samples
	res = y - yHat
	resCent = res-np.mean(res)
	ySample = np.zeros((nObs,nSamp))
	for i in range(nSamp):
		resSample = st.sampleWR(resCent)
		ySample[:,i] = yHat+resSample


	# residual bs time
	if estErr:
		sumErr = 0
		sumSqErr = 0
		sumNullErr = 0
		sumSqNullErr = 0

	sc = np.zeros(nRegs)
	sSqc = np.zeros(nRegs)
	ac = lil_matrix((nRegs,nSamp))
	sumSup = np.zeros(nRegs)
	

	for i in range(nSamp):
		# cv to get the errors
		if estErr:
			err,tmpEnm,tmpallVals = fitSampling(X,ySample[:,i],alpha,10,method='cv',lambdas=[lam])
			sumErr = err.mErr[0] + sumErr
			sumSqErr = err.mErr[0]**2 + sumSqErr
			# cv over this thing to get the null model errors
			nullErr,a = fitSamplingNull(ySample[:,i],10, method='cv')
			sumNullErr = sumNullErr + nullErr
			sumSqNullErr = sumSqNullErr + nullErr**2

		# need the coef
		# they change so we need to map the back to the original
		tmpEnm = enet.fit(X,ySample[:,i], alpha,lambdas=[lam])
		sc[tmpEnm.indices] = sc[tmpEnm.indices] + tmpEnm.coef[:,0]
		sSqc[tmpEnm.indices] = sSqc[tmpEnm.indices] + tmpEnm.coef[:,0]**2
		if len(tmpEnm.indices)>0:
			ac[tmpEnm.indices,i] = tmpEnm.coef
		# find supports 
		occur = np.zeros(len(tmpEnm.coef[:,0]))
		occur[abs(tmpEnm.coef[:,0])>1E-25] = 1.0
		sumSup[tmpEnm.indices] = sumSup[tmpEnm.indices] + occur
			

	# get averages and variances
	if estErr:
		aveErr = sumErr/nSamp
		sdErr = np.sqrt(sumSqErr/nSamp - aveErr**2)
		aveNullErr = sumNullErr/nSamp
		sdNullErr = np.sqrt(sumSqNullErr/nSamp - aveNullErr**2)

	aveCoef = sc/nSamp
	sdCoef = np.sqrt(sSqc/nSamp - aveCoef**2)
	#some crazy stuff here becase of the way scipy mat is shaped
	medCoef = np.array(np.median(ac.todense(),1))[:,0]
	pSup = sumSup/nSamp
	indices = np.arange(nRegs)[np.abs(medCoef)>1E-21]
	# put it in a dict for simplicity 
	solution = {}
	if estErr:
		solution['aveErr'] = aveErr
		solution['sdErr'] = sdErr
		solution['aveNullErr'] = aveNullErr
		solution['sdNullErr'] = sdNullErr

	solution['aveCoef'] = aveCoef
	solution['sdCoef'] = sdCoef
	solution['medCoef'] = medCoef
	solution['pSup'] = pSup
	solution['indices'] = indices
	
	nRegsHat = len(indices)
	if nRegsHat>0 and estImp:
		Xhat = X[:,indices]
		# lets do the leave one out importance deal
		errOutHat = np.zeros(nRegsHat) 
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

				errOutHat[j] = sumErr/nSamp

		elif nRegsHat==1:
			errOutHat[0] = aveNullErr

		# lets do leave only one
		errInHat = np.zeros(nRegsHat) 
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

			errInHat[j] = sumErr/nSamp

		errOut = np.zeros(nRegs)
		errOut[indices] = errOutHat
		solution['errOut'] = errOut
		errIn = np.zeros(nRegs)
		errIn[indices] = errInHat
		solution['errIn'] = errIn

	return solution, enm 







def select(X,y,nSamp=100,alphaList=np.array([1])):
	"""Select an elastic net model based 
	on a resampling method and return that
	model.
	"""
	nObs,nRegs = X.shape
	sdY = np.sqrt(np.var(y))
	# selection via bootstrap
	bestMin = 1E10
	for a in alphaList:
		tmpErr,tmpEnm,allVals = fitSampling(X,y,a,nSamp,method='bs')
		tmpErrV = tmpErr.mErr
		tmpMin = np.min(tmpErrV)
		
		if tmpMin < bestMin:
			bestMin = tmpMin
			modelIndex = np.argmin(tmpErrV)
			enm = tmpEnm
			err = tmpErr
			alpha = a
	
	# important values
		
	return enm[modelIndex]





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


