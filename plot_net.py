import sumolib
import matplotlib.pyplot as plt

net = sumolib.net.readNet('simulation/network/simpang4_pingit.net.xml.gz')

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_facecolor('#ffffff') # white background

# Plot the network
for edge in net.getEdges():
    for lane in edge.getLanes():
        shape = lane.getShape()
        x, y = zip(*shape)
        ax.plot(x, y, color='#171c27', linewidth=lane.getWidth() * 2)

# Remove axes
ax.axis('off')
plt.margins(0)
plt.savefig('frontend/public/sumo-bg.png', bbox_inches='tight', pad_inches=0, transparent=False)
print("Saved to sumo-bg.png")
