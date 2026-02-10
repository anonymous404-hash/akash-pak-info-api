// pages/api/number.js - Next.js API Route
export default async function handler(req, res) {
  // This is just a proxy to your Python backend
  const { num, key } = req.query;
  
  if (!num || !key) {
    return res.status(400).json({
      success: false,
      error: "Missing parameters. Use ?num=92...&key=..."
    });
  }
  
  // Forward to Python backend
  const backendUrl = process.env.BACKEND_URL || 'https://your-python-api.vercel.app';
  
  try {
    const response = await fetch(`${backendUrl}/api/number?num=${num}&key=${key}`);
    const data = await response.json();
    
    // Return the same response
    res.status(response.status).json(data);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: "Backend connection failed",
      detail: error.message
    });
  }
}
