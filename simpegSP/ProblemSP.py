from SimPEG import Problem, Utils, Maps, Mesh
from SimPEG.EM.Base import BaseEMProblem
from SimPEG.EM.Static.DC.FieldsDC import FieldsDC, Fields_CC
from SimPEG.EM.Static.DC import Survey, BaseDCProblem
from SimPEG.Utils import sdiag
import numpy as np
from SimPEG.Utils import Zero
from SimPEG.EM.Static.DC import getxBCyBC_CC

class SPPropMap(Maps.PropMap):

    """
        Property Map for IP Problems. The hydraulic head,
        H is the default inversion property
    """

    h = Maps.Property("Hydraulic Head", defaultInvProp = True)
    # L0 = 2.5*1e-4
    # L = Maps.Property("Crosss Coupling Coefficient", defaultInvProp = False)
	# Li = Maps.Property("Inverse Crosss Coupling Coefficient", defaultVal = 1./L0, propertyLink=('L', Maps.ReciprocalMap))


class BaseSPProblem(BaseDCProblem):

    surveyPair = Survey
    fieldsPair = FieldsDC
    PropMap = SPPropMap
    Ainv = None
    sigma = None
    rho = None
    f = None
    Ainv = None

    @property
    def deleteTheseOnModelUpdate(self):
        toDelete = []
        return toDelete

    # assume log rho or log cond
    @property
    def MeSigma(self):
        """
            Edge inner product matrix for \\(\\sigma\\). Used in the E-B formulation
        """
        if getattr(self, '_MeSigma', None) is None:
            self._MeSigma = self.mesh.getEdgeInnerProduct(self.sigma)
        return self._MeSigma

    @property
    def MfRhoI(self):
        """
            Inverse of :code:`MfRho`
        """
        if getattr(self, '_MfRhoI', None) is None:
            self._MfRhoI = self.mesh.getFaceInnerProduct(self.rho, invMat=True)
        return self._MfRhoI

    def MfRhoIDeriv(self,u):
        """
            Derivative of :code:`MfRhoI` with respect to the model.
        """

        dMfRhoI_dI = -self.MfRhoI**2
        dMf_drho = self.mesh.getFaceInnerProductDeriv(self.rho)(u)
        drho_dlogrho = Utils.sdiag(self.rho)*self.curModel.etaDeriv
        return dMfRhoI_dI * ( dMf_drho * ( drho_dlogrho))

    # TODO: This should take a vector
    def MeSigmaDeriv(self, u):
        """
            Derivative of MeSigma with respect to the model
        """
        dsigma_dlogsigma = Utils.sdiag(self.sigma)*self.curModel.etaDeriv
        return self.mesh.getEdgeInnerProductDeriv(self.sigma)(u) * dsigma_dlogsigma

class Problem_CC(BaseSPProblem):

    _solutionType = 'phiSolution'
    _formulation  = 'HJ' # CC potentials means J is on faces
    fieldsPair    = Fields_CC

    def __init__(self, mesh, **kwargs):
        BaseSPProblem.__init__(self, mesh, **kwargs)
        if self.rho is None:
        	raise Exception("Resistivity:rho needs to set when initializing SPproblem")
        self.setBC()

    def getA(self):
        """

        Make the A matrix for the cell centered DC resistivity problem

        A = D MfRhoI G

        """

        D = self.Div
        G = self.Grad
        MfRhoI = self.MfRhoI
        A = D * MfRhoI * G

        # I think we should deprecate this for DC problem.
        # if self._makeASymmetric is True:
        #     return V.T * A
        return A

    def getADeriv(self, u, v, adjoint= False):

        D = self.Div
        G = self.Grad
        MfRhoIDeriv = self.MfRhoIDeriv

        if adjoint:
            # if self._makeASymmetric is True:
            #     v = V * v
            return(MfRhoIDeriv( G * u ).T) * ( D.T * v)

        # I think we should deprecate this for DC problem.
        # if self._makeASymmetric is True:
        #     return V.T * ( D * ( MfRhoIDeriv( D.T * ( V * u ) ) * v ) )
        return D * (MfRhoIDeriv( G * u ) * v)

    def getRHS(self):
        """
        RHS for the DC problem

        q
        """

        RHS = self.getSourceTerm()

        # I think we should deprecate this for DC problem.
        # if self._makeASymmetric is True:
        #     return self.Vol.T * RHS

        return RHS

    def getRHSDeriv(self, src, v, adjoint=False):
        """
        Derivative of the right hand side with respect to the model
        """
        # TODO: add qDeriv for RHS depending on m
        # qDeriv = src.evalDeriv(self, adjoint=adjoint)
        # return qDeriv
        return Zero()

    def setBC(self):
        if self.mesh.dim==3:
            fxm,fxp,fym,fyp,fzm,fzp = self.mesh.faceBoundaryInd
            gBFxm = self.mesh.gridFx[fxm,:]
            gBFxp = self.mesh.gridFx[fxp,:]
            gBFym = self.mesh.gridFy[fym,:]
            gBFyp = self.mesh.gridFy[fyp,:]
            gBFzm = self.mesh.gridFz[fzm,:]
            gBFzp = self.mesh.gridFz[fzp,:]

            # Setup Mixed B.C (alpha, beta, gamma)
            temp_xm, temp_xp = np.ones_like(gBFxm[:,0]), np.ones_like(gBFxp[:,0])
            temp_ym, temp_yp = np.ones_like(gBFym[:,1]), np.ones_like(gBFyp[:,1])
            temp_zm, temp_zp = np.ones_like(gBFzm[:,2]), np.ones_like(gBFzp[:,2])

            alpha_xm, alpha_xp = temp_xm*0., temp_xp*0.
            alpha_ym, alpha_yp = temp_ym*0., temp_yp*0.
            alpha_zm, alpha_zp = temp_zm*0., temp_zp*0.

            beta_xm, beta_xp = temp_xm, temp_xp
            beta_ym, beta_yp = temp_ym, temp_yp
            beta_zm, beta_zp = temp_zm, temp_zp

            gamma_xm, gamma_xp = temp_xm*0., temp_xp*0.
            gamma_ym, gamma_yp = temp_ym*0., temp_yp*0.
            gamma_zm, gamma_zp = temp_zm*0., temp_zp*0.

            alpha = [alpha_xm, alpha_xp, alpha_ym, alpha_yp, alpha_zm, alpha_zp]
            beta =  [beta_xm, beta_xp, beta_ym, beta_yp, beta_zm, beta_zp]
            gamma = [gamma_xm, gamma_xp, gamma_ym, gamma_yp, gamma_zm, gamma_zp]

        elif self.mesh.dim==2:

            fxm,fxp,fym,fyp = self.mesh.faceBoundaryInd
            gBFxm = self.mesh.gridFx[fxm,:]
            gBFxp = self.mesh.gridFx[fxp,:]
            gBFym = self.mesh.gridFy[fym,:]
            gBFyp = self.mesh.gridFy[fyp,:]

            # Setup Mixed B.C (alpha, beta, gamma)
            temp_xm, temp_xp = np.ones_like(gBFxm[:,0]), np.ones_like(gBFxp[:,0])
            temp_ym, temp_yp = np.ones_like(gBFym[:,1]), np.ones_like(gBFyp[:,1])

            alpha_xm, alpha_xp = temp_xm*0., temp_xp*0.
            alpha_ym, alpha_yp = temp_ym*0., temp_yp*0.

            beta_xm, beta_xp = temp_xm, temp_xp
            beta_ym, beta_yp = temp_ym, temp_yp

            gamma_xm, gamma_xp = temp_xm*0., temp_xp*0.
            gamma_ym, gamma_yp = temp_ym*0., temp_yp*0.

            alpha = [alpha_xm, alpha_xp, alpha_ym, alpha_yp]
            beta =  [beta_xm, beta_xp, beta_ym, beta_yp]
            gamma = [gamma_xm, gamma_xp, gamma_ym, gamma_yp]

        x_BC, y_BC = getxBCyBC_CC(self.mesh, alpha, beta, gamma)
        V = self.Vol
        self.Div = V * self.mesh.faceDiv
        P_BC, B = self.mesh.getBCProjWF_simple()
        M = B*self.mesh.aveCC2F
        self.Grad = self.Div.T - P_BC*Utils.sdiag(y_BC)*M
