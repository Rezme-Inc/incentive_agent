"""
ROI Cycle - Iterative refinement of ROI calculations
"""
from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END

from src.core.config import settings
from .state import ROICycleState


class ROIAnalyzer:
    """Analyzes shortlisted programs and calculates ROI estimates"""

    def __init__(self):
        self.llm = ChatAnthropic(
            model=settings.claude_model,
            temperature=0.3,
            api_key=settings.anthropic_api_key
        )
        self.prompt = ChatPromptTemplate.from_template("""
You are an ROI analyst for employer hiring incentive programs.

Analyze this program and estimate potential ROI:
- Program: {program_name}
- Benefit Type: {benefit_type}
- Max Value: {max_value}
- Target Populations: {target_populations}

Previous answers (if any): {previous_answers}

Calculate:
1. Estimated value per hire (range)
2. Typical qualification rate
3. Administrative complexity (low/medium/high)
4. Time to receive benefit

Return JSON:
{{
    "estimated_value_per_hire": "$X - $Y",
    "qualification_rate": "X%",
    "complexity": "low|medium|high",
    "time_to_benefit": "X weeks/months",
    "confidence": "high|medium|low",
    "needs_more_info": ["list of info needed for refinement"]
}}
""")

    async def analyze(self, program: Dict, previous_answers: Dict) -> Dict:
        """Analyze a single program"""
        chain = self.prompt | self.llm | JsonOutputParser()

        try:
            result = await chain.ainvoke({
                "program_name": program.get("program_name", "Unknown"),
                "benefit_type": program.get("benefit_type", "unknown"),
                "max_value": program.get("max_value", "Unknown"),
                "target_populations": ", ".join(program.get("target_populations", [])),
                "previous_answers": str(previous_answers)
            })
            return {
                "program_id": program.get("id"),
                "program_name": program.get("program_name"),
                **result,
                "needs_refinement": len(result.get("needs_more_info", [])) > 0
            }
        except Exception as e:
            print(f"ROI analysis error: {e}")
            return {
                "program_id": program.get("id"),
                "program_name": program.get("program_name"),
                "error": str(e),
                "needs_refinement": True
            }


async def roi_analyzer_node(state: ROICycleState) -> Dict[str, Any]:
    """Analyze shortlist and calculate initial ROI estimates"""
    analyzer = ROIAnalyzer()
    calculations = []

    for prog in state.get("shortlisted_programs", []):
        try:
            prog_answers = {
                k: v for k, v in state.get("roi_answers", {}).items()
                if k.startswith(prog.get("id", ""))
            }
            calc = await analyzer.analyze(prog, prog_answers)
            calculations.append(calc)
        except Exception as e:
            print(f"ROI analyzer failed for {prog.get('program_name', 'unknown')}: {e}")
            calculations.append({
                "program_id": prog.get("id"),
                "program_name": prog.get("program_name"),
                "error": str(e),
                "needs_refinement": False,
            })

    return {"roi_calculations": calculations}


async def question_generator_node(state: ROICycleState) -> Dict[str, Any]:
    """Generate questions to refine ROI estimates"""
    questions = []
    calcs = state.get("roi_calculations", [])

    for calc in calcs:
        if not calc.get("needs_refinement"):
            continue

        prog_id = calc.get("program_id")
        prog_name = calc.get("program_name", "Unknown")
        needs_info = calc.get("needs_more_info", [])

        # Generate questions based on what's needed
        for info in needs_info:
            if "hire" in info.lower() or "employee" in info.lower():
                questions.append({
                    "program_id": prog_id,
                    "question_id": f"{prog_id}_num_hires",
                    "question": f"For {prog_name}: How many employees from target populations do you plan to hire in the next 12 months?",
                    "type": "number",
                    "required": True
                })
            elif "wage" in info.lower() or "salary" in info.lower():
                questions.append({
                    "program_id": prog_id,
                    "question_id": f"{prog_id}_avg_wage",
                    "question": f"For {prog_name}: What is the average hourly wage for these positions?",
                    "type": "currency",
                    "required": True
                })
            elif "retention" in info.lower():
                questions.append({
                    "program_id": prog_id,
                    "question_id": f"{prog_id}_retention",
                    "question": f"For {prog_name}: What is your expected employee retention rate after 6 months?",
                    "type": "percentage",
                    "required": False
                })

        # Default question if nothing specific
        if not needs_info:
            questions.append({
                "program_id": prog_id,
                "question_id": f"{prog_id}_general",
                "question": f"For {prog_name}: How many employees do you expect to hire who qualify for this program?",
                "type": "number",
                "required": True
            })

    return {"roi_questions": questions}


async def refinement_node(state: ROICycleState) -> Dict[str, Any]:
    """Process answers, refine calculations, check if done"""
    calcs = state.get("roi_calculations", [])
    answers = state.get("roi_answers", {})
    refined_calcs = []
    all_complete = True

    for calc in calcs:
        prog_id = calc.get("program_id")

        # Check if we have answers for this program
        prog_answers = {k: v for k, v in answers.items() if prog_id in k}

        if prog_answers:
            # Calculate refined ROI using answers
            num_hires = prog_answers.get(f"{prog_id}_num_hires", 0)
            avg_wage = prog_answers.get(f"{prog_id}_avg_wage", 15)

            # Simple ROI calculation (would be more sophisticated in production)
            estimated_value = calc.get("estimated_value_per_hire", "$0")
            try:
                # Parse value (e.g., "$2,400 - $9,600" -> average)
                import re
                values = re.findall(r'\$?([\d,]+)', estimated_value)
                if values:
                    avg_value = sum(int(v.replace(",", "")) for v in values) / len(values)
                    total_roi = avg_value * int(num_hires) if num_hires else 0
                else:
                    total_roi = 0
            except (ValueError, TypeError) as e:
                print(f"ROI parse error for {prog_id}: {e}")
                total_roi = 0

            refined_calcs.append({
                **calc,
                "refined_total_roi": f"${total_roi:,.0f}",
                "num_hires_used": num_hires,
                "needs_refinement": False
            })
        else:
            refined_calcs.append(calc)
            if calc.get("needs_refinement"):
                all_complete = False

    round_num = state.get("refinement_round", 0) + 1
    max_rounds = state.get("max_rounds", settings.max_roi_refinement_rounds)

    return {
        "roi_calculations": refined_calcs,
        "refinement_round": round_num,
        "is_complete": all_complete or round_num >= max_rounds
    }


def should_continue_roi(state: ROICycleState) -> str:
    """Conditional edge: continue cycle or exit"""
    if state.get("is_complete", False):
        return "exit"
    return "continue"


def create_roi_subgraph():
    """Create the ROI cycle subgraph"""
    workflow = StateGraph(ROICycleState)

    # Add nodes
    workflow.add_node("roi_analyzer", roi_analyzer_node)
    workflow.add_node("question_generator", question_generator_node)
    workflow.add_node("refinement", refinement_node)

    # Set entry point
    workflow.set_entry_point("roi_analyzer")

    # Linear flow through the cycle
    workflow.add_edge("roi_analyzer", "question_generator")
    workflow.add_edge("question_generator", "refinement")

    # Conditional: loop back or exit
    workflow.add_conditional_edges(
        "refinement",
        should_continue_roi,
        {
            "continue": "roi_analyzer",  # Loop back
            "exit": END  # Exit cycle
        }
    )

    return workflow.compile()
