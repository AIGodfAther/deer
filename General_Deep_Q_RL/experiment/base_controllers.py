"""This file defines the base Controller class and some presets controllers that you can use for controlling 
the training and the various parameters of your agents.

Controllers can be attached to an agent using the agent's attach(Controller) method. The order in which controllers 
are attached matters. Indeed, if controllers C1, C2 and C3 were attached in this order and C1 and C3 both listen to the
OnEpisodeEnd signal, the OnEpisodeEnd() method of C1 will be called *before* the OnEpisodeEnd() method of C3, whenever 
an episode ends.

Authors: Vincent Francois-Lavet, David Taralla
"""
from matplotlib import pyplot as plt
import numpy as np
import joblib
import os

class Controller(object):
    """A base controller that does nothing when receiving the various signals emitted by an agent. This class should 
    be the base class of any controller you would want to define.
    """

    def __init__(self):
        """Activate this controller.

        All controllers inheriting this class should call this method in their own __init()__ using 
        super(self.__class__, self).__init__().
        """

        self._active = True

    def setActive(self, active):
        """Activate or deactivate this controller.
        
        A controller should not react to any signal it receives as long as it is deactivated.
        """

        self._active = active

    def OnStart(self, agent):
        """Called when the agent is going to start working (before anything else).
        
        This corresponds to the moment where the agent's run() method is called.

        Parameters:
            agent [NeuralAgent] - The agent firing the event
        """

        pass

    def OnEpisodeEnd(self, agent, terminalReached, reward):
        """Called whenever the agent ends an episode, just after this episode ended and before any OnEpochEnd() signal
        could be sent.

        Parameters:
            agent [NeuralAgent] - The agent firing the event
            terminalReached [bool] - Whether the episode ended because a terminal transition occured. This could be 
                False if the episode was stopped because its step budget was exhausted.
            reward [number] - The reward obtained on the last transition performed in this episode.
        """

        pass

    def OnEpochEnd(self, agent):
        """Called whenever the agent ends an epoch, just after the last episode of this epoch was ended and after any 
        OnEpisodeEnd() signal was processed.

        Parameters:
            agent [NeuralAgent] - The agent firing the event
        """

        pass

    def OnActionChosen(self, agent, action):
        """Called whenever the agent has chosen an action.

        This occurs after the agent state was updated with the new observation it made, but before it applied this 
        action on the environment and before the total reward is updated.
        """

        pass

    def OnActionTaken(self, agent):
        """Called whenever the agent has taken an action on its environment.

        This occurs after the agent applied this action on the environment and before terminality is evaluated. This 
        is called only once, even in the case where the agent skip frames by taking the same action multiple times.
        In other words, this occurs just before the next observation of the environment.
        """

        pass

    def OnEnd(self, agent):
        """Called when the agent has finished processing all its epochs, just before returning from its run() method.
        """

        pass


class LearningRateController(Controller):
    """A controller that modifies the learning rate periodically upon epochs end."""

    def __init__(self, initialLearningRate, learningRateDecay, periodicity=1):
        """Initializer.

        Parameters:
            initialLearningRate [number] - The learning rate upon agent start
            learningRateDecay [number] - The factor by which the previous learning rate is multiplied every
                [periodicity] epochs.
            periodicity [int] - How many epochs are necessary before an update of the learning rate occurs
        """

        super(self.__class__, self).__init__()
        self._epochCount = 0
        self._initLr = initialLearningRate
        self._lr = initialLearningRate
        self._lrDecay = learningRateDecay
        self._periodicity = periodicity

    def OnStart(self, agent):
        if (self._active == False):
            return

        self._epochCount = 0
        agent.setLearningRate(self._initLr)
        self._lr = self._initLr * self._lrDecay

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        self._epochCount += 1
        if self._periodicity <= 1 or self._epochCount % self._periodicity == 0:
            agent.setLearningRate(self._lr)
            self._lr *= self._lrDecay


class EpsilonController(Controller):
    """A controller that modifies the probability "epsilon" of taking a random action periodically."""

    def __init__(self, initialE, eDecays, eMin, evaluateOn='action', periodicity=1, resetEvery='none'):
        """Initializer.

        Parameters:
            initialE [number] - Start epsilon
            eDecays [int] - How many updates are necessary for epsilon to reach eMin
            eMin [number] - End epsilon
            evaluateOn [str] - After what type of event epsilon shoud be updated periodically. Possible values: 
                'action', 'episode', 'epoch'.
            periodicity [int] - How many [evaluateOn] are necessary before an update of epsilon occurs
            resetEvery [str] - After what type of event epsilon should be reset to its initial value. Possible values: 
                'none', 'episode', 'epoch'.
        """

        super(self.__class__, self).__init__()
        self._count = 0
        self._initE = initialE
        self._e = initialE
        self._eMin = eMin
        self._eDecay = (initialE - eMin) / eDecays
        self._periodicity = periodicity

        self._onAction = 'action' == evaluateOn
        self._onEpisode = 'episode' == evaluateOn
        self._onEpoch = 'epoch' == evaluateOn
        if not self._onAction and not self._onEpisode and not self._onEpoch:
            self._onAction = True

        self._resetOnEpisode = 'episode' == resetEvery
        self._resetOnEpoch = 'epoch' == resetEvery

    def OnStart(self, agent):
        if (self._active == False):
            return

        self._reset(agent)

    def OnEpisodeEnd(self, agent, terminalReached, reward):
        if (self._active == False):
            return

        if self._resetOnEpisode:
           self. _reset(agent)
        elif self._onEpisode:
            self._update(agent)

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        if self._resetOnEpoch:
            self._reset(agent)
        elif self._onEpoch:
            self._update(agent)

    def OnActionChosen(self, agent, action):
        if (self._active == False):
            return

        if self._onAction:
            self._update(agent)


    def _reset(self, agent):
        self._count = 0
        agent.setEpsilon(self._initE)
        self._e = self._initE

    def _update(self, agent):
        self._count += 1
        if self._periodicity <= 1 or self._count % self._periodicity == 0:
            agent.setEpsilon(self._e)
            self._e = max(self._e - self._eDecay, self._eMin)



class DiscountFactorController(Controller):
    """A controller that modifies the qnetwork discount periodically."""

    def __init__(self, initialDiscountFactor, discountFactorGrowth, discountFactorMax=0.99, periodicity=1):
        """Initializer.

        Parameters:
            initialDiscountFactor [number] - Start discount
            discountFactorGrowth [number] - The factor by which the previous discount is multiplied every [periodicity]
                epochs.
            discountFactorMax [number] - Maximum reachable discount
            periodicity [int] - How many epochs are necessary before an update of the discount occurs
        """

        super(self.__class__, self).__init__()
        self._epochCount = 0
        self._initDF = initialDiscountFactor
        self._df = initialDiscountFactor
        self._dfGrowth = discountFactorGrowth
        self._dfMax = discountFactorGrowth
        self._periodicity = periodicity

    def OnStart(self, agent):
        if (self._active == False):
            return

        self._epochCount = 0
        agent.setDiscountFactor(self._initDF)
        if (self._initDF < self._dfMax):
            self._df = 1 - (1 - self._initDF) * self._dfGrowth
        else:
            self._df = self._initDF

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        self._epochCount += 1
        if self._periodicity <= 1 or self._epochCount % self._periodicity == 0:
            if (self._df < 0.99):
                agent.setDiscountFactor(self._df)
                self._df = 1 - (1 - self._df) * self._dfGrowth


class InterleavedTestEpochController(Controller):
    """A controller that interleaves a test epoch between training epochs of the agent.

    """
    def __init__(self, id, epochLength, controllersToDisable=[], periodicity=2, showScore=True, summarizeEvery=1):
        super(self.__class__, self).__init__()
        self._epochCount = 0
        self._id = id
        self._epochLength = epochLength
        self._toDisable = controllersToDisable
        self._showScore = showScore
        if periodicity <= 2:
            self._periodicity = 2
        else:
            self._periodicity = periodicity

        self._summaryCounter = 0
        self._summaryPeriodicity = summarizeEvery

    def OnStart(self, agent):
        if (self._active == False):
            return

        self._epochCount = 0
        self._summaryCounter = 0

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        mod = self._epochCount % self._periodicity
        self._epochCount += 1
        if mod == 0:
            agent.startMode(self._id, self._epochLength)
            agent.setControllersActive(self._toDisable, False)
        elif mod == 1:
            if self._showScore:
                print "Testing score (id: {}) is {}".format(self._id, agent.totalRewardOverLastTest())
            if self._summaryPeriodicity > 0 and self._summaryCounter % self._summaryPeriodicity == 0:
                agent.summarizeTestPerformance()
            self._summaryCounter += 1
            agent.resumeTrainingMode()
            agent.setControllersActive(self._toDisable, True)


class TrainerController(Controller):
    """A controller that make the agent train on its current database periodically.

    Arguments:
        evaluateOn - After what type of event the agent shoud be trained periodically ('action', 'episode', 'epoch').
        periodicity - How many steps of "evaluateOn" are necessary before a training occurs.
    """
    def __init__(self, evaluateOn='action', periodicity=1, showEpisodeAvgVValue=True, showAvgBellmanResidual=True):
        super(self.__class__, self).__init__()
        self._count = 0
        self._periodicity = periodicity
        self._showAvgBellmanResidual = showAvgBellmanResidual
        self._showEpisodeAvgVValue = showEpisodeAvgVValue

        self._onAction = 'action' == evaluateOn
        self._onEpisode = 'episode' == evaluateOn
        self._onEpoch = 'epoch' == evaluateOn
        if not self._onAction and not self._onEpisode and not self._onEpoch:
            self._onAction = True

    def OnStart(self, agent):
        if (self._active == False):
            return
        
        self._count = 0

    def OnEpisodeEnd(self, agent, terminalReached, reward):
        if (self._active == False):
            return
        
        if self._onEpisode:
            self._update(agent)

        if self._showAvgBellmanResidual: print "Episode average bellman residual): {}".format(agent.avgBellmanResidual())
        if self._showEpisodeAvgVValue: print "Episode average V value: {}".format(agent.avgEpisodeVValue())

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        if self._onEpoch:
            self._update(agent)

    def OnActionTaken(self, agent):
        if (self._active == False):
            return

        if self._onAction:
            self._update(agent)

    def _update(self, agent):
        self._count += 1
        if self._periodicity <= 1 or self._count % self._periodicity == 0:
            agent.train()
            

class VerboseController(Controller):
    """A controller that make the agent train on its current database periodically.

    Arguments:
        evaluateOn - After what type of event the agent shoud be trained periodically ('action', 'episode', 'epoch').
        periodicity - How many steps of "evaluateOn" are necessary before a training occurs.
    """
    def __init__(self, evaluateOn='epoch', periodicity=1):
        super(self.__class__, self).__init__()
        self._count = 0
        self._periodicity = periodicity
        self._string = evaluateOn

        self._onAction = 'action' == evaluateOn
        self._onEpisode = 'episode' == evaluateOn
        self._onEpoch = 'epoch' == evaluateOn
        if not self._onAction and not self._onEpisode and not self._onEpoch:
            self._onEpoch = True

    def OnStart(self, agent):
        if (self._active == False):
            return
        
        self._count = 0

    def OnEpisodeEnd(self, agent, terminalReached, reward):
        if (self._active == False):
            return
        
        if self._onEpisode:
            self._print(agent)

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        if self._onEpoch:
            self._print(agent)

    def OnActionTaken(self, agent):
        if (self._active == False):
            return

        if self._onAction:
            self._print(agent)

    def _print(self, agent):
        if self._periodicity <= 1 or self._count % self._periodicity == 0:
            print "{} {}:".format(self._string, self._count + 1)
            print "Learning rate: {}".format(agent.learningRate())
            print "Discount factor: {}".format(agent.discountFactor())
            print "Epsilon: {}".format(agent.epsilon())
        self._count += 1

class FindBestController(Controller):
    def __init__(self, validationID, testID, unique_fname="nnet", showPlot=False):
        super(self.__class__, self).__init__()

        self._validationScores = []
        self._testScores = []
        self._epochNumbers = []
        self._epochCount = 0
        self._testID = testID
        self._validationID = validationID
        self._filename = unique_fname
        self._showPlot = showPlot
        self._bestValidationScoreSoFar = -9999999

    def OnEpochEnd(self, agent):
        if (self._active == False):
            return

        mode = agent.mode()
        if mode == self._validationID:
            score = agent.totalRewardOverLastTest()
            self._validationScores.append(score)
            if score > self._bestValidationScoreSoFar:
                self._bestValidationScoreSoFar = score
                agent.dumpNetwork(self._filename, self._epochCount)
        elif mode == self._testID:
            self._testScores.append(agent.totalRewardOverLastTest())
            self._epochNumbers.append(self._epochCount)
        else:
            self._epochCount += 1
        
    def OnEnd(self, agent):
        if (self._active == False):
            return

        bestIndex = np.argmax(self._validationScores)
        print "Best neural net obtained after {} epochs, with validation score {}".format(self._epochNumbers[bestIndex], self._validationScores[bestIndex])
        print "Test score of this neural net: {}".format(self._testScores[bestIndex])

        plt.plot(self._epochNumbers, self._validationScores, label="VS", color='b')
        plt.plot(self._epochNumbers, self._testScores, label="TS", color='r')
        plt.legend()
        plt.xlabel("n_epochs")
        plt.ylabel("Score")

        
        try:
            os.mkdir("scores")
        except Exception:
            pass
        basename = "scores/" + self._filename
        joblib.dump({"n": self._epochNumbers, "vs": self._validationScores, "ts": self._testScores}, basename + "_scores.jldump")
        plt.savefig(basename + "_scores.pdf")
        if self._showPlot:
            plt.show()


if __name__ == "__main__":
    pass
