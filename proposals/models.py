from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel

class Proposal(BaseModel):
    """Model for citizen proposals with voting and rewards."""
    
    class Status(models.TextChoices):
        """Proposal status choices."""
        DRAFT = 'draft', _('Draft')
        ACTIVE = 'active', _('Active')
        UNDER_REVIEW = 'under_review', _('Under Review')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        IMPLEMENTED = 'implemented', _('Implemented')
        
    class Category(models.TextChoices):
        """Proposal category choices."""
        INFRASTRUCTURE = 'infrastructure', _('Infrastructure')
        EDUCATION = 'education', _('Education')
        HEALTHCARE = 'healthcare', _('Healthcare')
        SECURITY = 'security', _('Security')
        ENVIRONMENT = 'environment', _('Environment')
        ECONOMY = 'economy', _('Economy')
        SOCIAL = 'social', _('Social Services')
        OTHER = 'other', _('Other')
    
    title = models.CharField(
        _('title'),
        max_length=200,
        help_text=_('Title of the proposal')
    )
    description = models.TextField(
        _('description'),
        help_text=_('Detailed description of the proposal')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text=_('Current status of the proposal')
    )
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=Category.choices,
        help_text=_('Category of the proposal')
    )
    location = models.ForeignKey(
        'core.Location',
        on_delete=models.PROTECT,
        related_name='proposals',
        help_text=_('Location this proposal is for')
    )
    landmark = models.ForeignKey(
        'core.Landmark',
        on_delete=models.PROTECT,
        related_name='proposals',
        null=True,
        blank=True,
        help_text=_('Specific landmark this proposal is for (optional)')
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['location']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = _('proposal')
        verbose_name_plural = _('proposals')
        
    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'
        
    @property
    def is_votable(self) -> bool:
        """Check if proposal is in a votable status."""
        return self.status in [self.Status.DRAFT, self.Status.ACTIVE]

class Vote(BaseModel):
    """Model for votes on proposals."""
    
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name='votes',
        help_text=_('Proposal being voted on')
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='votes',
        help_text=_('User who voted')
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['proposal', 'user']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['proposal', 'user'],
                name='unique_proposal_vote'
            )
        ]
        verbose_name = _('vote')
        verbose_name_plural = _('votes')
        
    def __str__(self):
        return f'Vote by {self.user.username} on {self.proposal.title}'
        
    def save(self, *args, **kwargs):
        """Ensure proposal is votable before saving vote."""
        if not self.proposal.is_votable:
            raise ValueError('Cannot vote on a proposal that is not in draft or active status')
        super().save(*args, **kwargs)

class Reward(BaseModel):
    """Model for rewards given for proposal actions."""
    
    class ActionType(models.TextChoices):
        """Reward action type choices."""
        PROPOSAL_CREATED = 'proposal_created', _('Proposal Created')
        VOTE_ADDED = 'vote_added', _('Vote Added')
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='rewards',
        help_text=_('User receiving the reward')
    )
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name='rewards',
        help_text=_('Proposal the reward is for')
    )
    amount = models.PositiveIntegerField(
        _('amount'),
        validators=[MinValueValidator(1)],
        help_text=_('Amount of reward points')
    )
    action_type = models.CharField(
        _('action type'),
        max_length=20,
        choices=ActionType.choices,
        help_text=_('Type of action that earned the reward')
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['proposal']),
            models.Index(fields=['action_type']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = _('reward')
        verbose_name_plural = _('rewards')
        
    def __str__(self):
        return f'{self.get_action_type_display()} reward of {self.amount} points for {self.user.username}'