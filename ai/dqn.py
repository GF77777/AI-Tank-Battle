"""DQN：Q 网络（MLP）、经验回放、Double DQN 智能体。"""

import random

import numpy as np
import torch
import torch.nn as nn


class QNet(nn.Module):
    """MLP：state_dim -> 256 -> 256 -> n_actions，ReLU。"""

    def __init__(self, state_dim, n_actions, hidden=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, x):
        return self.net(x)


class ReplayBuffer:
    """定长循环经验回放池，numpy 存储。"""

    def __init__(self, capacity, state_dim):
        self.capacity = capacity
        self.states = np.zeros((capacity, state_dim), dtype=np.float32)
        self.next_states = np.zeros((capacity, state_dim), dtype=np.float32)
        self.actions = np.zeros(capacity, dtype=np.int64)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self.idx = 0
        self.size = 0

    def push(self, state, action, reward, next_state, done):
        i = self.idx
        self.states[i] = state
        self.actions[i] = action
        self.rewards[i] = reward
        self.next_states[i] = next_state
        self.dones[i] = float(done)
        self.idx = (self.idx + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size):
        idx = np.random.randint(0, self.size, size=batch_size)
        return (self.states[idx], self.actions[idx], self.rewards[idx],
                self.next_states[idx], self.dones[idx])

    def __len__(self):
        return self.size


class DQNAgent:
    """Double DQN：online net 选动作、target net 估值，target 每 sync_interval 步硬更新。"""

    def __init__(self, state_dim, n_actions, lr=1e-3, gamma=0.99,
                 buffer_capacity=100_000, batch_size=64, sync_interval=1000,
                 device=None):
        self.n_actions = n_actions
        self.gamma = gamma
        self.batch_size = batch_size
        self.sync_interval = sync_interval
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.online = QNet(state_dim, n_actions).to(self.device)
        self.target = QNet(state_dim, n_actions).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=lr)
        self.loss_fn = nn.SmoothL1Loss()  # Huber loss
        self.buffer = ReplayBuffer(buffer_capacity, state_dim)
        self.learn_steps = 0

    def act(self, state, epsilon):
        """ε-greedy 选动作。"""
        if random.random() < epsilon:
            return random.randrange(self.n_actions)
        with torch.no_grad():
            s = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            return int(self.online(s).argmax(dim=1).item())

    def store(self, state, action, reward, next_state, done):
        self.buffer.push(state, action, reward, next_state, done)

    def learn(self):
        """采样一个 batch 做一次梯度更新，返回 loss（样本不足时返回 None）。"""
        if len(self.buffer) < self.batch_size:
            return None
        s, a, r, ns, d = self.buffer.sample(self.batch_size)
        s = torch.as_tensor(s, device=self.device)
        a = torch.as_tensor(a, device=self.device)
        r = torch.as_tensor(r, device=self.device)
        ns = torch.as_tensor(ns, device=self.device)
        d = torch.as_tensor(d, device=self.device)

        q = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            next_a = self.online(ns).argmax(dim=1, keepdim=True)      # online 选动作
            next_q = self.target(ns).gather(1, next_a).squeeze(1)     # target 估值
            target_q = r + self.gamma * next_q * (1.0 - d)
        loss = self.loss_fn(q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.learn_steps += 1
        if self.learn_steps % self.sync_interval == 0:
            self.target.load_state_dict(self.online.state_dict())
        return float(loss.item())

    def save(self, path):
        torch.save({"online": self.online.state_dict()}, path)

    def load(self, path):
        ckpt = torch.load(path, map_location=self.device, weights_only=True)
        old = ckpt["online"]
        new = self.online.state_dict()
        # 宽容加载：首层输入维变宽（如毒圈扩维 260->262）时，
        # 旧权重复制到前 N 列，新增列保持随机初始化，已学知识不浪费
        for k, v in old.items():
            if v.shape == new[k].shape:
                new[k] = v
            elif len(v.shape) == 2 and v.shape[0] == new[k].shape[0] and v.shape[1] < new[k].shape[1]:
                new[k][:, :v.shape[1]] = v
                print(f"[dqn] 首层扩维迁移: {k} {tuple(v.shape)} -> {tuple(new[k].shape)}")
            else:
                raise RuntimeError(f"[dqn] 无法迁移的层: {k} {tuple(v.shape)} vs {tuple(new[k].shape)}")
        self.online.load_state_dict(new)
        self.target.load_state_dict(new)
