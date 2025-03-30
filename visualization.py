import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime
import calendar

# Database file path
DATABASE = 'history.db'

def create_interest_chart():
    """
    Creates a bar chart of top interests based on browser history.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        # Get category counts
        query = """
        SELECT category, COUNT(*) as count
        FROM history
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            # Return empty figure if no data
            fig = go.Figure()
            fig.update_layout(
                title="No interest data available",
                xaxis_title="Category",
                yaxis_title="Count"
            )
            return fig
            
        # Create bar chart
        fig = px.bar(
            df,
            x='category',
            y='count',
            color='category',
            title='Your Top Interests',
            labels={'category': 'Interest Category', 'count': 'Number of Visits'},
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
        
        # Update layout
        fig.update_layout(
            xaxis_title="Interest Category",
            yaxis_title="Number of Visits",
            xaxis={'categoryorder':'total descending'},
            showlegend=False
        )
        
        return fig
    except Exception as e:
        print(f"Error creating interest chart: {str(e)}")
        # Return empty figure on error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading interest data: {str(e)}",
            xaxis_title="Category",
            yaxis_title="Count"
        )
        return fig

def create_domain_chart():
    """
    Creates a pie chart of most visited domains.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        # Get domain counts
        query = """
        SELECT domain, COUNT(*) as count
        FROM history
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 8
        """
        df = pd.read_sql_query(query, conn)
        
        # Get total count for "Others" category
        total_query = "SELECT COUNT(*) FROM history"
        total_count = pd.read_sql_query(total_query, conn).iloc[0, 0]
        
        conn.close()
        
        if df.empty:
            # Return empty figure if no data
            fig = go.Figure()
            fig.update_layout(title="No domain data available")
            return fig
            
        # Calculate the sum of the top domains
        top_domains_sum = df['count'].sum()
        
        # Add "Others" category if there are more domains than the top ones
        if total_count > top_domains_sum:
            others_df = pd.DataFrame({
                'domain': ['Others'],
                'count': [total_count - top_domains_sum]
            })
            df = pd.concat([df, others_df], ignore_index=True)
        
        # Create pie chart
        fig = px.pie(
            df,
            names='domain',
            values='count',
            title='Most Visited Domains',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        
        # Update layout
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            legend_title="Domain",
            legend=dict(orientation="h", y=-0.1)
        )
        
        return fig
    except Exception as e:
        print(f"Error creating domain chart: {str(e)}")
        # Return empty figure on error
        fig = go.Figure()
        fig.update_layout(title=f"Error loading domain data: {str(e)}")
        return fig

def create_time_pattern_chart():
    """
    Creates a heatmap showing browsing patterns by day of week and hour of day.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        # Get all visit times
        query = "SELECT visit_time FROM history"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            # Return empty figure if no data
            fig = go.Figure()
            fig.update_layout(title="No time pattern data available")
            return fig
            
        # Convert visit_time to datetime and extract day of week and hour
        df['datetime'] = pd.to_datetime(df['visit_time'], errors='coerce')
        df = df.dropna(subset=['datetime'])  # Drop rows with invalid datetime
        
        if df.empty:
            # Return empty figure if no valid datetime data
            fig = go.Figure()
            fig.update_layout(title="No valid time data available")
            return fig
            
        df['day_of_week'] = df['datetime'].dt.day_name()
        df['hour'] = df['datetime'].dt.hour
        
        # Create a pivot table for the heatmap
        pivot_table = df.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
        
        # Convert day_of_week to categorical with proper order
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        pivot_table['day_of_week'] = pd.Categorical(pivot_table['day_of_week'], categories=days_order, ordered=True)
        
        # Sort by the categorical day of week
        pivot_table = pivot_table.sort_values('day_of_week')
        
        # Create a pivot table for the heatmap
        heatmap_data = pivot_table.pivot(index='day_of_week', columns='hour', values='count')
        
        # Fill NaN with 0
        heatmap_data = heatmap_data.fillna(0)
        
        # Create heatmap
        fig = px.imshow(
            heatmap_data,
            labels=dict(x="Hour of Day", y="Day of Week", color="Visit Count"),
            x=list(range(24)),  # 0-23 hours
            y=days_order,
            color_continuous_scale='Viridis',
            title='Browsing Activity by Day and Hour'
        )
        
        # Update layout
        fig.update_layout(
            xaxis_title="Hour of Day",
            yaxis_title="Day of Week",
            coloraxis_colorbar=dict(title="Visit Count")
        )
        
        # Add hour annotations
        hour_labels = [f"{h}:00" for h in range(24)]
        fig.update_xaxes(tickvals=list(range(24)), ticktext=hour_labels)
        
        return fig
    except Exception as e:
        print(f"Error creating time pattern chart: {str(e)}")
        # Return empty figure on error
        fig = go.Figure()
        fig.update_layout(title=f"Error loading time pattern data: {str(e)}")
        return fig

def create_history_timeline():
    """
    Creates a timeline of website visits by category.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        query = """
        SELECT website_name, category, visit_time, domain
        FROM history
        ORDER BY visit_time DESC
        LIMIT 100
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            # Return empty figure if no data
            fig = go.Figure()
            fig.update_layout(title="No timeline data available")
            return fig
            
        # Convert visit_time to datetime
        df['visit_time'] = pd.to_datetime(df['visit_time'], errors='coerce')
        df = df.dropna(subset=['visit_time'])  # Drop rows with invalid datetime
        
        if df.empty:
            # Return empty figure if no valid datetime data
            fig = go.Figure()
            fig.update_layout(title="No valid timeline data available")
            return fig
            
        # Sort by time
        df = df.sort_values('visit_time')
        
        # Create a timeline
        fig = px.scatter(
            df,
            x='visit_time',
            y='category',
            color='category',
            hover_name='website_name',
            hover_data=['domain'],
            title='Your Browsing Timeline',
            labels={
                'visit_time': 'Date & Time',
                'category': 'Category',
                'website_name': 'Website',
                'domain': 'Domain'
            },
            height=500
        )
        
        # Update layout for better readability
        fig.update_layout(
            xaxis_title="Date & Time",
            yaxis_title="Category",
            yaxis={'categoryorder':'total ascending'},
            hoverlabel=dict(bgcolor="white", font_size=12)
        )
        
        # Add markers
        fig.update_traces(marker=dict(size=10, line=dict(width=2, color='DarkSlateGrey')))
        
        return fig
    except Exception as e:
        print(f"Error creating timeline: {str(e)}")
        # Return empty figure on error
        fig = go.Figure()
        fig.update_layout(title=f"Error loading timeline data: {str(e)}")
        return fig
