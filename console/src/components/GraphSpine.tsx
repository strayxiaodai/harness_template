import { GRAPH_NODES } from '../types/api'
import type { GraphNode } from '../types/api'
import './GraphSpine.css'

interface GraphSpineProps {
  activeNode: string | null
  completedNodes: Set<string>
  refineFrom: string | null
  onSelectNode: (node: GraphNode) => void
}

function graphNodeLabel(
  node: string,
  isActive: boolean,
  isDone: boolean,
): string {
  if (isActive) {
    return `${node}, active step`
  }
  if (isDone) {
    return `${node}, completed`
  }
  return `${node}, pending`
}

export function GraphSpine({
  activeNode,
  completedNodes,
  refineFrom,
  onSelectNode,
}: GraphSpineProps) {
  return (
    <section className="graph-spine panel" aria-label="Agent graph">
      <h2 className="panel-title">Graph spine</h2>
      <p className="graph-spine__scroll-hint">Scroll horizontally for the full flow</p>
      <div
        className="graph-spine__track"
        tabIndex={0}
        aria-label="Graph node list, scroll horizontally on small screens"
      >
        <svg
          className="graph-spine__svg"
          viewBox="0 0 720 120"
          role="img"
          aria-label="LangGraph node flow"
        >
          <defs>
            <marker
              id="arrow"
              markerWidth="8"
              markerHeight="8"
              refX="6"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L6,3 L0,6 Z" fill="var(--muted)" />
            </marker>
          </defs>
          {GRAPH_NODES.slice(0, -1).map((node, index) => {
            const x1 = 60 + index * 130
            const x2 = x1 + 90
            return (
              <line
                key={`edge-${node}`}
                x1={x1}
                y1={60}
                x2={x2}
                y2={60}
                className="graph-spine__edge"
                markerEnd="url(#arrow)"
              />
            )
          })}
          {(refineFrom === 'planner' || refineFrom === 'executor') && (
            <path
              d="M 580 78 Q 360 110 70 78"
              className="graph-spine__loop"
              fill="none"
              markerEnd="url(#arrow)"
            />
          )}
        </svg>
        <ol className="graph-spine__nodes">
          {GRAPH_NODES.map((node) => {
            const isActive = activeNode === node
            const isDone = completedNodes.has(node)
            return (
              <li key={node}>
                <button
                  type="button"
                  className={`graph-node ${
                    isActive ? 'graph-node--active' : ''
                  } ${isDone ? 'graph-node--done' : ''}`}
                  onClick={() => onSelectNode(node)}
                  aria-current={isActive ? 'step' : undefined}
                  aria-label={graphNodeLabel(node, isActive, isDone)}
                >
                  <span className="graph-node__dot" aria-hidden />
                  {node}
                </button>
              </li>
            )
          })}
        </ol>
      </div>
    </section>
  )
}
