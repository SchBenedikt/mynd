"""
Knowledge Graph Engine - Builds and manages a semantic knowledge graph from various data sources.
Extracts entities (people, tasks, projects, documents, organizations) and their relationships.
"""

import json
import os
import re
import hashlib
from typing import Dict, List, Set, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import threading

# Graph Constants
NODE_TYPES = {
    "PERSON": "person",
    "EVENT": "event",
    "TASK": "task",
    "ORGANIZATION": "organization",
    "DOCUMENT": "document",
    "PROJECT": "project",
    "MEETING": "meeting",
}

EDGE_TYPES = {
    "PARTICIPATES_IN": "participates_in",
    "ASSIGNED_TO": "assigned_to",
    "MENTIONED_IN": "mentioned_in",
    "RELATED_TO": "related_to",
    "CREATED_BY": "created_by",
    "OWNS": "owns",
    "WORKS_WITH": "works_with",
    "COMMUNICATES_WITH": "communicates_with",
    "ATTACHED_TO": "attached_to",
    "DEPENDS_ON": "depends_on",
}


class KnowledgeGraph:
    """Manages entity extraction and relationship building from multiple data sources."""

    MAX_GRAPH_FILE_SIZE_BYTES = 50 * 1024 * 1024
    
    def __init__(self, graph_file: str = None):
        self.graph_file = graph_file or "data/knowledge_graph.json"
        self.nodes: Dict[str, Dict[str, Any]] = {}  # node_id -> {type, label, properties, created_at, updated_at}
        self.edges: List[Dict[str, Any]] = []  # List of {from, to, type, properties, created_at}
        self.lock = threading.RLock()
        self.last_update = None
        self.load_graph()
    
    def _create_node_id(self, node_type: str, value: str) -> str:
        """Create unique node ID from type and value."""
        # Normalize: lowercase, replace spaces with underscores
        normalized = re.sub(r'[^a-z0-9_]', '', value.lower().replace(' ', '_'))
        digest = hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]
        return f"{node_type.lower()}:{normalized}:{digest}"
    
    def add_node(self, node_type: str, label: str, properties: Dict = None, 
                 deduplicate_key: str = None) -> str:
        """Add a node to the graph. Returns node_id."""
        if deduplicate_key is None:
            deduplicate_key = label
        
        node_id = self._create_node_id(node_type, deduplicate_key)
        
        if node_id not in self.nodes:
            with self.lock:
                self.nodes[node_id] = {
                    "id": node_id,
                    "type": node_type,
                    "label": label,
                    "properties": properties or {},
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
        else:
            # Update existing node
            with self.lock:
                if properties:
                    self.nodes[node_id]["properties"].update(properties)
                self.nodes[node_id]["updated_at"] = datetime.now().isoformat()
        
        return node_id
    
    def add_edge(self, from_id: str, to_id: str, edge_type: str, properties: Dict = None) -> None:
        """Add an edge between two nodes."""
        if from_id not in self.nodes or to_id not in self.nodes:
            return  # Don't add edges to non-existent nodes
        
        # Check if edge already exists
        edge_key = (from_id, to_id, edge_type)
        existing = any(
            e["from"] == from_id and e["to"] == to_id and e["type"] == edge_type
            for e in self.edges
        )
        
        if not existing:
            with self.lock:
                self.edges.append({
                    "from": from_id,
                    "to": to_id,
                    "type": edge_type,
                    "properties": properties or {},
                    "created_at": datetime.now().isoformat(),
                })

    def _extract_topics(self, text: str, limit: int = 3) -> List[str]:
        """Extract a small set of reusable topic tokens from a free-text value."""
        cleaned_text = (text or '').lower()
        tokens = re.findall(r"[a-z0-9äöüß]{4,}", cleaned_text)
        stopwords = {
            'and', 'the', 'oder', 'und', 'von', 'mit', 'für', 'fuer', 'die', 'der', 'das',
            'to', 'for', 'from', 'file', 'final', 'copy', 'draft', 'scan', 'image', 'note',
            're', 'fw', 'ref', 'reply', 'subject', 'email', 'mail', 'task'
        }

        topics = []
        for token in tokens:
            if token in stopwords or token in topics:
                continue
            topics.append(token)
            if len(topics) >= limit:
                break
        return topics
    
    def extract_from_calendar(self, calendar_events: List[Dict]) -> None:
        """Extract entities and relationships from calendar events."""
        if not calendar_events:
            return
        
        for event in calendar_events:
            # Create event node
            event_id = self.add_node(
                NODE_TYPES["EVENT"],
                event.get("summary", "Unnamed Event"),
                {
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                    "description": event.get("description", "")[:200],
                    "location": event.get("location", ""),
                    "source": "calendar"
                },
                deduplicate_key=f"{event.get('summary', '')}{event.get('start', '')}"
            )
            
            # Extract participants
            attendees = event.get("attendees", [])
            for attendee in attendees:
                name = attendee.get("common_name") or attendee.get("cn") or attendee.get("email", "Unknown")
                email = attendee.get("email", "")
                
                person_id = self.add_node(
                    NODE_TYPES["PERSON"],
                    name,
                    {"email": email, "source": "calendar"},
                    deduplicate_key=email if email else name
                )
                
                # Link person to event
                self.add_edge(person_id, event_id, EDGE_TYPES["PARTICIPATES_IN"])
            
            # Extract organization from location if possible
            location = event.get("location", "")
            if location and len(location) > 2:
                org_id = self.add_node(
                    NODE_TYPES["ORGANIZATION"],
                    location,
                    {"source": "calendar"}
                )
                self.add_edge(event_id, org_id, EDGE_TYPES["RELATED_TO"])
    
    def extract_from_emails(self, emails: List[Dict]) -> None:
        """Extract entities and relationships from emails."""
        if not emails:
            return
        
        for email_msg in emails:
            # Create email-related nodes
            sender = email_msg.get("from", "Unknown")
            recipients = email_msg.get("to", [])
            subject = email_msg.get("subject", "No Subject")
            
            # Create sender person node
            sender_id = self.add_node(
                NODE_TYPES["PERSON"],
                sender,
                {"email": sender, "source": "email"},
                deduplicate_key=sender
            )

            for topic in self._extract_topics(subject):
                topic_id = self.add_node(
                    NODE_TYPES["PROJECT"],
                    topic,
                    {"source": "email", "kind": "topic"},
                    deduplicate_key=f"topic:{topic}"
                )
                self.add_edge(sender_id, topic_id, EDGE_TYPES["MENTIONED_IN"])
            
            # Create recipient person nodes and relationships
            for recipient in recipients:
                recipient_id = self.add_node(
                    NODE_TYPES["PERSON"],
                    recipient,
                    {"email": recipient, "source": "email"},
                    deduplicate_key=recipient
                )
                
                # Create communication edge
                self.add_edge(sender_id, recipient_id, EDGE_TYPES["COMMUNICATES_WITH"])
            
            # Extract document reference if there are attachments
            attachments = email_msg.get("attachments", [])
            for attachment in attachments:
                doc_id = self.add_node(
                    NODE_TYPES["DOCUMENT"],
                    attachment.get("filename", "attachment"),
                    {
                        "size": attachment.get("size", 0),
                        "mime_type": attachment.get("mime_type", ""),
                        "source": "email"
                    }
                )
                self.add_edge(doc_id, sender_id, EDGE_TYPES["CREATED_BY"])
    
    def extract_from_tasks(self, tasks: List[Dict]) -> None:
        """Extract entities and relationships from tasks/todos."""
        if not tasks:
            return
        
        for task in tasks:
            task_id = self.add_node(
                NODE_TYPES["TASK"],
                task.get("title", "Unnamed Task"),
                {
                    "description": task.get("description", "")[:200],
                    "due_date": task.get("due_date", ""),
                    "status": task.get("status", "open"),
                    "priority": task.get("priority", "normal"),
                    "source": "tasks"
                },
                deduplicate_key=f"{task.get('title', '')}{task.get('due_date', '')}"
            )

            for topic in self._extract_topics(task.get("title", "")):
                topic_id = self.add_node(
                    NODE_TYPES["PROJECT"],
                    topic,
                    {"source": "tasks", "kind": "topic"},
                    deduplicate_key=f"topic:{topic}"
                )
                self.add_edge(task_id, topic_id, EDGE_TYPES["RELATED_TO"])
            
            # Link to assignee if available
            assignee = task.get("assigned_to")
            if assignee:
                person_id = self.add_node(
                    NODE_TYPES["PERSON"],
                    assignee,
                    {"source": "tasks"},
                    deduplicate_key=assignee
                )
                self.add_edge(task_id, person_id, EDGE_TYPES["ASSIGNED_TO"])
            
            # Link to related events by matching dates
            due_date = task.get("due_date", "")
            if due_date:
                related_events = [
                    n for n in self.nodes.values()
                    if n["type"] == NODE_TYPES["EVENT"] and due_date in n["properties"].get("start", "")
                ]
                for event_node in related_events:
                    self.add_edge(task_id, event_node["id"], EDGE_TYPES["RELATED_TO"])
    
    def extract_from_documents(self, documents: List[Dict]) -> None:
        """Extract entities and relationships from documents."""
        if not documents:
            return
        folder_cache = {}

        def get_folder_node(folder_path: str) -> str:
            folder_path = (folder_path or '').strip()
            if not folder_path:
                return ''
            if folder_path in folder_cache:
                return folder_cache[folder_path]

            folder_name = os.path.basename(folder_path.rstrip('/\\')) or folder_path
            folder_id = self.add_node(
                NODE_TYPES["PROJECT"],
                folder_name,
                {
                    "path": folder_path,
                    "kind": "folder",
                    "source": "documents"
                },
                deduplicate_key=f"folder:{folder_path}"
            )
            folder_cache[folder_path] = folder_id

            parent_folder = os.path.dirname(folder_path.rstrip('/\\'))
            if parent_folder and parent_folder != folder_path:
                parent_folder_id = get_folder_node(parent_folder)
                if parent_folder_id and parent_folder_id != folder_id:
                    self.add_edge(folder_id, parent_folder_id, EDGE_TYPES["RELATED_TO"])

            return folder_id

        for doc in documents:
            doc_name = doc.get("name", "Unnamed Document")
            doc_path = doc.get("path", "")
            file_type = str(doc.get("mime_type") or doc.get("file_type") or '').lower().strip()
            doc_id = self.add_node(
                NODE_TYPES["DOCUMENT"],
                doc_name,
                {
                    "path": doc_path,
                    "size": doc.get("size", 0),
                    "mime_type": file_type,
                    "file_type": file_type,
                    "modified": doc.get("modified", ""),
                    "chunk_count": doc.get("chunk_count", 0),
                    "source": doc.get("source", "documents")
                },
                deduplicate_key=doc.get("path", doc.get("name", ""))
            )

            folder_path = os.path.dirname(doc_path) if doc_path else ""
            if folder_path:
                folder_id = get_folder_node(folder_path)
                if folder_id:
                    self.add_edge(doc_id, folder_id, EDGE_TYPES["RELATED_TO"])

            if file_type:
                type_label = file_type.split('/')[-1] if '/' in file_type else file_type
                type_id = self.add_node(
                    NODE_TYPES["PROJECT"],
                    type_label,
                    {"source": "documents", "kind": "file_type"},
                    deduplicate_key=f"file_type:{type_label}"
                )
                self.add_edge(doc_id, type_id, EDGE_TYPES["RELATED_TO"])
            
            # Extract tags/categories from filename
            filename = doc_name
            # Look for patterns like [tag] or #tag in filename
            tags = re.findall(r'[\[\#]([^\]\#]+)[\]\#]', filename)
            for tag in tags:
                project_id = self.add_node(
                    NODE_TYPES["PROJECT"],
                    tag.strip(),
                    {"source": "documents", "kind": "tag"},
                    deduplicate_key=f"tag:{tag.strip().lower()}"
                )
                self.add_edge(doc_id, project_id, EDGE_TYPES["RELATED_TO"])

            for topic in self._extract_topics(os.path.splitext(filename)[0]):
                topic_id = self.add_node(
                    NODE_TYPES["PROJECT"],
                    topic,
                    {"source": "documents", "kind": "topic"},
                    deduplicate_key=f"topic:{topic}"
                )
                self.add_edge(doc_id, topic_id, EDGE_TYPES["RELATED_TO"])
    
    def build_co_occurrence_relationships(self) -> None:
        """Build relationships based on entities appearing together in multiple contexts."""
        # Find people who appear together in multiple events
        people_in_events = defaultdict(set)
        
        for edge in self.edges:
            if edge["type"] == EDGE_TYPES["PARTICIPATES_IN"]:
                person_id = edge["from"]
                event_id = edge["to"]
                people_in_events[event_id].add(person_id)
        
        # Create "works_with" edges for people in the same event
        for event_id, people in people_in_events.items():
            people_list = list(people)
            for i, person1 in enumerate(people_list):
                for person2 in people_list[i + 1:]:
                    # Check if edge already exists
                    self.add_edge(person1, person2, EDGE_TYPES["WORKS_WITH"])
    
    def get_graph_data(self) -> Dict[str, Any]:
        """Return current graph as dictionary suitable for JSON serialization and frontend."""
        with self.lock:
            return {
                "nodes": list(self.nodes.values()),
                "edges": self.edges,
                "stats": {
                    "node_count": len(self.nodes),
                    "edge_count": len(self.edges),
                    "node_types": self._count_by_type(self.nodes),
                    "edge_types": self._count_edge_types(self.edges),
                    "last_update": self.last_update or datetime.now().isoformat(),
                }
            }
    
    def _count_by_type(self, nodes: Dict) -> Dict[str, int]:
        """Count nodes by type."""
        counts = defaultdict(int)
        for node in nodes.values():
            counts[node["type"]] += 1
        return dict(counts)
    
    def _count_edge_types(self, edges: List) -> Dict[str, int]:
        """Count edges by type."""
        counts = defaultdict(int)
        for edge in edges:
            counts[edge["type"]] += 1
        return dict(counts)
    
    def save_graph(self) -> None:
        """Persist graph to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.graph_file), exist_ok=True)
            with self.lock:
                data = self.get_graph_data()
                with open(self.graph_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            self.last_update = datetime.now().isoformat()
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")
    
    def load_graph(self) -> None:
        """Load graph from JSON file."""
        if not os.path.exists(self.graph_file):
            return

        try:
            if os.path.getsize(self.graph_file) > self.MAX_GRAPH_FILE_SIZE_BYTES:
                print(f"Knowledge graph file too large, skipping load: {self.graph_file}")
                return
        except OSError as e:
            print(f"Error checking knowledge graph size: {e}")
            return
        
        try:
            with open(self.graph_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self.lock:
                self.nodes = {}
                self.edges = []
                
                # Reconstruct nodes
                for node in data.get("nodes", []):
                    self.nodes[node["id"]] = node
                
                # Reconstruct edges
                self.edges = data.get("edges", [])
                
                if data.get("stats"):
                    self.last_update = data["stats"].get("last_update")
        except Exception as e:
            print(f"Error loading knowledge graph: {e}")
    
    def query_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Query all nodes of a specific type."""
        return [node for node in self.nodes.values() if node["type"] == node_type]
    
    def get_related_nodes(self, node_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get all nodes connected to a given node up to max_depth hops away."""
        try:
            max_depth = int(max_depth)
        except (TypeError, ValueError):
            max_depth = 2

        visited = set()
        result = {"nodes": {}, "edges": []}
        
        def traverse(current_id: str, depth: int):
            if depth == 0 or current_id in visited:
                return
            visited.add(current_id)
            
            if current_id in self.nodes:
                result["nodes"][current_id] = self.nodes[current_id]
            
            # Find all edges connected to this node
            for edge in self.edges:
                if edge["from"] == current_id:
                    result["edges"].append(edge)
                    traverse(edge["to"], depth - 1)
                elif edge["to"] == current_id:
                    result["edges"].append(edge)
                    traverse(edge["from"], depth - 1)
        
        traverse(node_id, max_depth)
        return result
    
    def clear(self) -> None:
        """Clear the entire graph."""
        with self.lock:
            self.nodes.clear()
            self.edges.clear()
            self.last_update = None
    
    def update_from_data_sources(self, data_sources: Dict[str, List]) -> None:
        """Update graph from multiple data sources in one call."""
        calendar_events = data_sources.get("calendar_events", [])
        emails = data_sources.get("emails", [])
        tasks = data_sources.get("tasks", [])
        documents = data_sources.get("documents", [])

        self.clear()
        
        self.extract_from_calendar(calendar_events)
        self.extract_from_emails(emails)
        self.extract_from_tasks(tasks)
        self.extract_from_documents(documents)
        self.build_co_occurrence_relationships()
        self.save_graph()


# Global instance
_knowledge_graph = None

def get_knowledge_graph(graph_file: str = None) -> KnowledgeGraph:
    """Get or create the global knowledge graph instance."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph(graph_file)
    return _knowledge_graph
