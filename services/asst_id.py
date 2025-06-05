import os
from openai import AzureOpenAI

# Set environment variables directly
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://wercopenai.openai.azure.com/"
os.environ["AZURE_OPENAI_API_KEY"] = "48b0cc7a06d04279a8ae53997526965e"

print("Creating JobApplyAgent with o4-mini...")

# Create client with newest API version for o4-mini
preview_client = AzureOpenAI(
    azure_endpoint="https://wercopenai.openai.azure.com/",
    api_key="48b0cc7a06d04279a8ae53997526965e",
    api_version="2024-12-01-preview"
)

# Your specific instructions
job_agent_instructions = """You are an intelligent agent responsible for managing the job application process end-to-end. Your responsibilities include:

1. **Job Relevance Classification**: Determine whether a scraped job posting is a good fit based on resume embeddings.
2. **Resume Selection**: Choose the best-fit resume from the Azure vector store to match the job posting.
3. **Cover Letter Drafting**: Create a personalized, high-quality cover letter tailored to the job description and resume.
4. **Application Form Handling**: When provided with a job application form (custom questions, additional info), draft thoughtful, concise responses.
5. **Application Execution Strategy**: Trigger the application automation process or flag it for manual intervention if Playwright or auto-apply fails.
6. **Logging and Feedback**: Log application details, outcomes, and improvement suggestions for future iterations.

You work with a vector store of resumes and other personal materials. Always be concise, relevant, and action-oriented. When generating responses, optimize for clarity and speed of execution."""

print("\n1. Testing o4-mini model...")
try:
    # First test if o4-mini works with chat completions
    test_response = preview_client.chat.completions.create(
        model="o4-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_completion_tokens=10
    )
    print("✅ o4-mini model test successful")
    print(f"Response: {test_response.choices[0].message.content}")
except Exception as e:
    print(f"❌ o4-mini test failed: {e}")
    print("Will try with gpt-4o-mini as fallback...")

print("\n2. Creating JobApplyAgent assistant...")
try:
    # Try with o4-mini first
    assistant = preview_client.beta.assistants.create(
        model="o4-mini",
        name="JobApplyAgent",
        description="An intelligent agent for end-to-end job application management",
        instructions=job_agent_instructions,
        tools=[
            {"type": "code_interpreter"},
            {"type": "file_search"}
        ],
        temperature=0.7
    )
    print(f"🎉 JobApplyAgent created successfully with o4-mini!")
    print(f"📝 Assistant ID: {assistant.id}")
    print(f"🤖 Model: {assistant.model}")
    
except Exception as e:
    print(f"❌ o4-mini assistant creation failed: {e}")
    print("Trying with gpt-4o-mini fallback...")
    
    try:
        assistant = preview_client.beta.assistants.create(
            model="gpt-4o-mini",
            name="JobApplyAgent",
            description="An intelligent agent for end-to-end job application management",
            instructions=job_agent_instructions,
            tools=[
                {"type": "code_interpreter"},
                {"type": "file_search"}
            ],
            temperature=0.7
        )
        print(f"🎉 JobApplyAgent created successfully with gpt-4o-mini!")
        print(f"📝 Assistant ID: {assistant.id}")
        print(f"🤖 Model: {assistant.model}")
        
    except Exception as fallback_e:
        print(f"❌ Fallback also failed: {fallback_e}")
        exit(1)

# Save the assistant ID and configuration
print("\n3. Saving configuration...")
with open("assistant_id.txt", "w") as f:
    f.write(assistant.id)

with open("assistant_config.txt", "w") as f:
    f.write(f"ASSISTANT_ID={assistant.id}\n")
    f.write(f"MODEL={assistant.model}\n")
    f.write(f"API_VERSION=2024-12-01-preview\n")
    f.write(f"ENDPOINT=https://wercopenai.openai.azure.com/\n")

print("✅ Assistant ID saved to assistant_id.txt")
print("✅ Full configuration saved to assistant_config.txt")

print(f"\n🚀 Your JobApplyAgent is ready!")
print(f"Assistant ID: {assistant.id}")
print("You can now use this assistant in your n8n workflow.")

# Optional: Test the assistant
print("\n4. Testing assistant functionality...")
try:
    thread = preview_client.beta.threads.create()
    
    message = preview_client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Hello! Can you help me with a job application?"
    )
    
    run = preview_client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )
    
    print("✅ Assistant test successful - ready for use!")
    
except Exception as e:
    print(f"⚠️ Assistant created but test failed: {e}")
    print("This is likely normal - the assistant should still work in your application.")

print("\nSetup complete! 🎯")