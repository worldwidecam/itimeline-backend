# Legacy features that have been deprecated
# Kept for reference purposes only

"""
Post Promotion System
This system was originally designed to promote posts to events based on user votes and other metrics.
Removed due to changing requirements and simplified event creation approach.
"""

class PostPromotionSystem:
    def calculate_promotion_score(self, post):
        base_score = post.upvotes
        comment_bonus = len(post.comments) * 0.5
        source_bonus = post.source_count * 2
        content_bonus = min(len(post.content) / 500, 2)
        promotion_bonus = post.promotion_votes * 1.5
        
        return base_score + comment_bonus + source_bonus + content_bonus + promotion_bonus

    def check_promotions(self, timeline_id, threshold=10.0):
        """Check posts for potential promotion to events"""
        posts = Post.query.filter_by(
            timeline_id=timeline_id, 
            promoted_to_event=False
        ).all()
        
        promoted_posts = []
        for post in posts:
            score = self.calculate_promotion_score(post)
            if score >= threshold:
                promoted_posts.append(post)
                
        return promoted_posts

    def vote_for_promotion(self, post_id, user_id):
        """Vote to promote a post to an event"""
        post = Post.query.get_or_404(post_id)
        post.promotion_votes += 1
        post.update_promotion_score()
        return post.promotion_score

# Related database columns that can be removed:
"""
In Post model:
- promoted_to_event = db.Column(db.Boolean, default=False)
- promotion_score = db.Column(db.Float, default=0.0)
- source_count = db.Column(db.Integer, default=0)
- promotion_votes = db.Column(db.Integer, default=0)
- last_score_update = db.Column(db.DateTime, default=datetime.now())
"""
