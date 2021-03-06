import numpy as np
import torch
import torch.nn.functional as F

from garage.core import Serializable

from sandbox.zhanpeng.torch.core.networks import MLP
from sandbox.zhanpeng.torch.policies import StochasticPolicy


class GaussianMLPPolicy(StochasticPolicy, Serializable):

    def __init__(self,
                 obs_dim,
                 action_dim,
                 name="GaussianMLPPolicy",
                 hidden_sizes=(32, 32),
                 learn_std=True,
                 init_std=1.0,
                 adaptive_std=False,
                 std_share_network=False,
                 std_hidden_sizes=(32, 32),
                 min_std=1e-6,
                 std_hidden_nonlinearity=F.tanh,
                 hidden_nonlinearity=F.tanh,
                 output_nonlinearity=None,
                 mean_network=None,
                 std_network=None,
                 std_parametrization='exp'):

        Serializable.quick_init(self, locals())

        obs_dim = obs_dim
        action_dim = action_dim

        self._std_share_network = std_share_network
        self._action_dim = action_dim

        if mean_network is None:
            if std_share_network:
                if std_parametrization == "exp":
                    init_std_param = np.log(init_std)
                elif std_parametrization == "softplus":
                    init_std_param = np.log(np.exp(init_std) - 1)
                else:
                    raise NotImplementedError
                # TODO: if sharing network, only the bias of the std is using init_b
                mean_network = MLP(
                    input_size=obs_dim,
                    output_size=2*action_dim,
                    hidden_sizes=hidden_sizes,
                    hidden_nonlinearity=hidden_nonlinearity,
                    output_nonlinearity=output_nonlinearity,
                    init_b=init_std_param,
                )
            else:
                mean_network = MLP(
                    input_size=obs_dim,
                    output_size=action_dim,
                    hidden_sizes=hidden_sizes,
                    hidden_nonlinearity=hidden_nonlinearity,
                    output_nonlinearity=output_nonlinearity,
                )
        self._mean_network = mean_network

        if std_network is None:
            if adaptive_std:
                if not std_share_network:
                    # TODO: There should be an init value for std
                    std_network = MLP(
                        input_size=obs_dim,
                        output_size=action_dim,
                        hidden_sizes=std_hidden_sizes,
                        hidden_nonlinearity=std_hidden_nonlinearity,
                        output_nonlinearity=output_nonlinearity,
                    )
            else:
                if std_parametrization == "exp":
                    init_std_param = np.log(init_std)
                elif std_parametrization == "softplus":
                    init_std_param = np.log(np.exp(init_std) - 1)
                else:
                    raise NotImplementedError

                std_network = torch.Tensor(np.full((action_dim,), init_std_param))  # TODO: Check the gradient of this
        self._std_network = std_network

        self._dist = torch.distributions.Normal  # TODO: Check other approach..currently create tensor on the fly

    def get_action(self, observation):
        mean, std = self._get_mean_and_std(observation)
        dist = self._dist(loc=mean, scale=std)
        action = dist.sample()  # TODO: Check sample shape
        log_prob = dist.log_prob(action)

        return action, dict(log_prob=log_prob)

    def _get_mean_and_std(self, observation):
        if self._std_share_network:
            mean_and_std = self._mean_network(observation)
            mean, std = np.split(mean_and_std, self._action_dim, axis=10)
        else:
            mean = self._mean_network(observation)
            std = self._mean_network(observation)

        return mean, std

