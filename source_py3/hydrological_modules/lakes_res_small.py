# -------------------------------------------------------------------------
# Name:        Small Lakes and reservoirs module
#              (watershed provided < 5000 km2 or lakearea < 100km2)
# Purpose:
#
# Author:      PB
#
# Created:     30/08/2017
# Copyright:   (c) PB 2017
# -------------------------------------------------------------------------

from management_modules.data_handling import *
from hydrological_modules.routing_reservoirs.routing_sub import *


from management_modules.globals import *


class lakes_res_small(object):
    """
    LAKES AND RESERVOIRS
    calculate water retention in lakes and reservoirs
    """

    def __init__(self, lakes_res_small_variable):
        self.var = lakes_res_small_variable


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------


    def initial(self):
        """
        Initialize small lakes and reservoirs
        Read parameters from maps e.g
        area, location, initial average discharge, type: reservoir or lake) etc.

        """



        if checkOption('includeWaterBodies') and returnBool('useSmallLakes'):



            if returnBool('useResAndLakes') and returnBool('dynamicLakesRes'):
                year = datetime.datetime(dateVar['currDate'].year, 1, 1)
            else:
                year =  datetime.datetime(int(binding['fixLakesResYear']), 1, 1)


            # read which part of the cellarea is a lake/res catchment (sumed up for all lakes/res in a cell)
            self.var.smallpart = readnetcdf2('smallLakesRes', year, useDaily="yearly",  value= 'watershedarea') *1000 * 1000
            self.var.smallpart = self.var.smallpart  / self.var.cellArea
            self.var.smallpart = np.minimum(1., self.var.smallpart)

            self.var.smalllakeArea = readnetcdf2('smallLakesRes', year, useDaily="yearly",  value= 'area') * 1000 * 1000

			

            # lake discharge at outlet to calculate alpha: parameter of channel width, gravity and weir coefficient
            # Lake parameter A (suggested  value equal to outflow width in [m])
            # multiplied with the calibration parameter LakeMultiplier
            testRunoff = "averageRunoff" in binding
            if testRunoff:
                self.var.smalllakeDis0 = loadmap('averageRunoff') *  self.var.smallpart * self.var.cellArea * self.var.InvDtSec
            else:
                self.var.smalllakeDis0 = loadmap('smallwaterBodyDis')
            self.var.smalllakeDis0 = np.maximum(self.var.smalllakeDis0, 0.01)
            chanwidth = 7.1 * np.power(self.var.smalllakeDis0, 0.539)
            self.var.smalllakeA = loadmap('lakeAFactor') * 0.612 * 2 / 3 * chanwidth * (2 * 9.81) ** 0.5



            #Initial part of the lakes module
            #Using the **Modified Puls approach** to calculate retention of a lake
            # See also: LISFLOOD manual Annex 3 (Burek et al. 2013)

            # for Modified Puls Method the Q(inflow)1 has to be used. It is assumed that this is the same as Q(inflow)2 for the first timestep
            # has to be checked if this works in forecasting mode!

            # NEW Lake Routine using Modified Puls Method (see Maniak, p.331ff)
            # (Qin1 + Qin2)/2 - (Qout1 + Qout2)/2 = (S2 - S1)/dtime
            # changed into:
            # (S2/dtime + Qout2/2) = (S1/dtime + Qout1/2) - Qout1 + (Qin1 + Qin2)/2
            # outgoing discharge (Qout) are linked to storage (S) by elevation.
            # Now some assumption to make life easier:
            # 1.) storage volume is increase proportional to elevation: S = A * H
            #      H: elevation, A: area of lake
            # 2.) outgoing discharge = c * b * H **2.0 (c: weir constant, b: width)
            #      2.0 because it fits to a parabolic cross section see Aigner 2008
            #      (and it is much easier to calculate (that's the main reason)
            # c for a perfect weir with mu=0.577 and Poleni: 2/3 mu * sqrt(2*g) = 1.7
            # c for a parabolic weir: around 1.8
            # because it is a imperfect weir: C = c* 0.85 = 1.5
            # results in a formular : Q = 1.5 * b * H ** 2 = a*H**2 -> H = sqrt(Q/a)
            self.var.smalllakeFactor = self.var.smalllakeArea / (self.var.DtSec * np.sqrt(self.var.smalllakeA))

            #  solving the equation  (S2/dtime + Qout2/2) = (S1/dtime + Qout1/2) - Qout1 + (Qin1 + Qin2)/2
            #  SI = (S2/dtime + Qout2/2) =  (A*H)/DtRouting + Q/2 = A/(DtRouting*sqrt(a)  * sqrt(Q) + Q/2
            #  -> replacement: A/(DtRouting*sqrt(a)) = Lakefactor, Y = sqrt(Q)
            #  Y**2 + 2*Lakefactor*Y-2*SI=0
            # solution of this quadratic equation:
            # Q=sqr(-LakeFactor+sqrt(sqr(LakeFactor)+2*SI))

            self.var.smalllakeFactorSqr = np.square(self.var.smalllakeFactor)
            # for faster calculation inside dynamic section

            self.var.smalllakeInflowOld = self.var.init_module.load_initial("smalllakeInflow",self.var.smalllakeDis0)  # inflow in m3/s estimate
            
            old = self.var.smalllakeArea * np.sqrt(self.var.smalllakeInflowOld / self.var.smalllakeA)
            self.var.smalllakeVolumeM3 = self.var.init_module.load_initial("smalllakeStorage",old)


            smalllakeStorageIndicator = np.maximum(0.0,self.var.smalllakeVolumeM3 / self.var.DtSec + self.var.smalllakeInflowOld / 2)
            out = np.square(-self.var.smalllakeFactor + np.sqrt(self.var.smalllakeFactorSqr + 2 * smalllakeStorageIndicator))
            # SI = S/dt + Q/2
            # solution of quadratic equation
            # 1. storage volume is increase proportional to elevation
            #  2. Q= a *H **2.0  (if you choose Q= a *H **1.5 you have to solve the formula of Cardano)
            self.var.smalllakeOutflow = self.var.init_module.load_initial("smalllakeOutflow", out)

            # lake storage ini
            self.var.smalllakeLevel = divideValues(self.var.smalllakeVolumeM3, self.var.smalllakeArea)

            self.var.smalllakeStorage = self.var.smalllakeVolumeM3.copy()


            testStorage = "minStorage" in binding
            if testStorage:
                self.var.minsmalllakeVolumeM3 = loadmap('minStorage')
            else:
                self.var.minsmalllakeVolumeM3 = 9.e99







   # ------------------ End init ------------------------------------------------------------------------------------
   # ----------------------------------------------------------------------------------------------------------------




    def dynamic(self):
        """
        Dynamic part to calculate outflow from small lakes and reservoirs

        * lakes with modified Puls approach
        * reservoirs with special filling levels
        :return: outflow in m3 to the network
        """

        def dynamic_smalllakes(inflow):
            """
            Lake routine to calculate lake outflow
            :param inflow: inflow to lakes and reservoirs
            :return: QLakeOutM3DtC - lake outflow in [m3] per subtime step
            """

            # ************************************************************
            # ***** LAKE
            # ************************************************************


            if checkOption('calcWaterBalance'):
                self.var.preSmalllakeStorage = self.var.smalllakeStorage.copy()

            #if (dateVar['curr'] == 998):
            #    ii = 1

            inflowM3S = inflow / self.var.DtSec
            # Lake inflow in [m3/s]
            lakeIn = (inflowM3S + self.var.smalllakeInflowOld) * 0.5
            # for Modified Puls Method: (S2/dtime + Qout2/2) = (S1/dtime + Qout1/2) - Qout1 + (Qin1 + Qin2)/2
            # here: (Qin1 + Qin2)/2
            self.var.smallLakeIn = lakeIn * self.var.DtSec /self.var.cellArea  # in [m]

            self.var.smallevapWaterBody = self.var.lakeEvaFactor * self.var.EWRef * self.var.smalllakeArea
            self.var.smallevapWaterBody = np.where((self.var.smalllakeVolumeM3 - self.var.smallevapWaterBody) > 0., self.var.smallevapWaterBody, self.var.smalllakeVolumeM3)
            self.var.smalllakeVolumeM3 = self.var.smalllakeVolumeM3 - self.var.smallevapWaterBody
            # lakestorage - evaporation from lakes

            self.var.smalllakeInflowOld = inflowM3S.copy()
            # Qin2 becomes Qin1 for the next time step

            lakeStorageIndicator = np.maximum(0.0,self.var.smalllakeVolumeM3 / self.var.DtSec  - 0.5 * self.var.smalllakeOutflow + lakeIn)

            # here S1/dtime - Qout1/2 + lakeIn , so that is the right part
            # of the equation above

            self.var.smalllakeOutflow = np.square(-self.var.smalllakeFactor + np.sqrt(self.var.smalllakeFactorSqr + 2 * lakeStorageIndicator))

            # Flow out of lake:
            #  solving the equation  (S2/dtime + Qout2/2) = (S1/dtime + Qout1/2) - Qout1 + (Qin1 + Qin2)/2
            #  SI = (S2/dtime + Qout2/2) =  (A*H)/DtSec + Q/2 = A/(DtSec*sqrt(a)  * sqrt(Q) + Q/2
            #  -> replacement: A/(DtSec*sqrt(a)) = Lakefactor, Y = sqrt(Q)
            #  Y**2 + 2*Lakefactor*Y-2*SI=0
            # solution of this quadratic equation:
            # Q=sqr(-LakeFactor+sqrt(sqr(LakeFactor)+2*SI));

            QsmallLakeOut = self.var.smalllakeOutflow * self.var.DtSec

            self.var.smalllakeVolumeM3 = (lakeStorageIndicator - self.var.smalllakeOutflow * 0.5) * self.var.DtSec
            # Lake storage

            self.var.smalllakeStorage =  self.var.smalllakeStorage + lakeIn * self.var.DtSec  - QsmallLakeOut - self.var.smallevapWaterBody
            # for mass balance, the lake storage is calculated every time step

            ### if dateVar['curr'] >= dateVar['intSpin']:
            ###   self.var.minsmalllakeStorageM3 = np.where(self.var.smalllakeStorageM3 < self.var.minsmalllakeStorageM3,self.var.smalllakeStorageM3,self.var.minsmalllakeStorageM3)

            self.var.smallevapWaterBody = self.var.smallevapWaterBody / self.var.cellArea # back to [m]
            self.var.smalllakeLevel = divideValues(self.var.smalllakeVolumeM3, self.var.smalllakeArea)


            if checkOption('calcWaterBalance'):
                self.var.waterbalance_module.waterBalanceCheck(
                    [self.var.smallLakeIn],  # In
                    [QsmallLakeOut / self.var.cellArea ,self.var.smallevapWaterBody ]  ,  # Out
                    [self.var.preSmalllakeStorage / self.var.cellArea],  # prev storage
                    [self.var.smalllakeStorage / self.var.cellArea],
                    "smalllake", False)



            return QsmallLakeOut

        # ---------------------------------------------------------------------------------------------
        # ---------------------------------------------------------------------------------------------



        # ---------------------------------------------------------------------------------------------
        # ---------------------------------------------------------------------------------------------
        # Small lake and reservoirs

        if checkOption('includeWaterBodies') and returnBool('useSmallLakes'):



            # check years
            if dateVar['newStart'] or dateVar['newYear']:
               
                if returnBool('useResAndLakes') and returnBool('dynamicLakesRes'):
                    year = datetime.datetime(dateVar['currDate'].year, 1, 1)
                else:
                    year = datetime.datetime(int(binding['fixLakesResYear']), 1, 1)
                self.var.smallpart = readnetcdf2('smallLakesRes', year, useDaily="yearly",  value= 'watershedarea') *1000 * 1000
                self.var.smallpart = self.var.smallpart  / self.var.cellArea
                self.var.smallpart = np.minimum(1., self.var.smallpart)

                self.var.smalllakeArea = readnetcdf2('smallLakesRes', year, useDaily="yearly",  value= 'area') *1000 * 1000
                # mult with 1,000,000 to convert from km2 to m2



            # ----------
            # inflow lakes
            # 1.  dis = upstream1(self.var.downstruct_LR, self.var.discharge)   # from river upstream
            # 2.  runoff = npareatotal(self.var.waterBodyID, self.var.waterBodyID)  # from cell itself
            # 3.                  # outflow from upstream lakes

            # ----------

            # runoff to the lake as a part of the cell basin
            inflow = self.var.smallpart * self.var.runoff * self.var.cellArea  # inflow in m3
            self.var.smallLakeout = dynamic_smalllakes(inflow) / self.var.cellArea     # back to [m]

            self.var.smallLakeDiff =   self.var.smallpart * self.var.runoff - self.var.smallLakeIn
            self.var.smallrunoffDiff = self.var.smallpart * self.var.runoff - self.var.smallLakeout

            self.var.runoff = self.var.smallLakeout + (1-self.var.smallpart) * self.var.runoff    # back to [m]  # with and without in m3


            # ------------------------------------------------------------
            #report(decompress(runoff_LR), "C:\work\output3/run.map")

            if checkOption('calcWaterBalance'):
                self.var.waterbalance_module.waterBalanceCheck(
                    [self.var.smallLakeIn],  # In
                    [self.var.smallLakeout,  self.var.smallevapWaterBody],  # Out
                    [self.var.preSmalllakeStorage / self.var.cellArea],  # prev storage
                    [self.var.smalllakeStorage / self.var.cellArea],
                    "smalllake1", False)

            return



# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
