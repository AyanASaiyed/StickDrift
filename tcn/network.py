"""Lightweight non-causal temporal convolutional network.

The recording is scored offline, so each layer looks both backward and forward.
Three independent sigmoids produce resemblance scores. Nothing in the head
forces those scores to add up to 100.
"""

import torch
from torch import nn

from tcn.config import DROPOUT, HIDDEN, KERNEL, LEVELS


class TemporalBlock(nn.Module):
    def __init__(self, channels: int, kernel: int, dilation: int, dropout: float):
        super().__init__()
        padding = dilation * (kernel - 1) // 2
        self.conv1 = nn.Conv1d(channels, channels, kernel, padding=padding, dilation=dilation)
        self.norm1 = nn.GroupNorm(_groups(channels), channels)
        self.conv2 = nn.Conv1d(channels, channels, kernel, padding=padding, dilation=dilation)
        self.norm2 = nn.GroupNorm(_groups(channels), channels)
        self.drop = nn.Dropout(dropout)
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.drop(self.act(self.norm1(self.conv1(x))))
        y = self.drop(self.act(self.norm2(self.conv2(y))))
        if y.shape[-1] != x.shape[-1]:
            y = y[..., : x.shape[-1]]
        return self.act(x + y)


class PatternTCN(nn.Module):
    def __init__(
        self,
        in_channels: int,
        hidden: int = HIDDEN,
        levels: int = LEVELS,
        kernel: int = KERNEL,
        dropout: float = DROPOUT,
        n_scores: int = 3,
    ):
        super().__init__()
        self.in_channels = in_channels
        self.hidden = hidden
        self.levels = levels
        self.kernel = kernel
        self.dropout = dropout
        self.in_proj = nn.Conv1d(in_channels, hidden, kernel_size=1)
        self.blocks = nn.ModuleList(
            TemporalBlock(hidden, kernel, 2**level, dropout) for level in range(levels)
        )
        self.head = nn.Linear(hidden, n_scores)

    def forward(self, x: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        """Score a batch.

        `x` is (batch, channels, time). `mask` is (batch, time), 1 on real
        samples and 0 on padding. Returns (batch, 3) scores in (0, 100).
        """
        hidden = self.in_proj(x)
        for block in self.blocks:
            hidden = block(hidden)
        if mask is None:
            pooled = hidden.mean(dim=-1)
        else:
            weights = mask.unsqueeze(1)
            pooled = (hidden * weights).sum(dim=-1) / weights.sum(dim=-1).clamp(min=1.0)
        return torch.sigmoid(self.head(pooled)) * 100.0


def _groups(channels: int) -> int:
    for size in (8, 4, 2, 1):
        if channels % size == 0:
            return size
    return 1
