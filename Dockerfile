FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
# Copy only source files; never include a developer's database or credentials.
COPY app.py races.py skill_tree.py swarm.py swarm_ai.py accounts.py onboarding.py backups.py i18n.py galaxies.py run.py ./
COPY en.json pl.json de.json es.json fr.json ./
EXPOSE 8080
CMD ["python", "run.py"]
